from dataclasses import dataclass, field
from gc import is_finalized
from pathlib import Path
from socket import AF_INET, AF_NETBEUI, inet_ntop
from struct import pack
from threading import Lock, Thread
from typing import Any, Optional, Union, cast

from bcc import BPF
from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.tracing.probes.common import BaseProbe, EventCallback


@dataclass
class ProbeOptions(DataclassConversionMixin):

    sport: Optional[int] = field(default=None)
    """If not `None`, trace this source port only. Equivalent to the original `--sport` option."""

    dport: Optional[int] = field(default=None)
    """If not `None`, trace this destination port only. Equivalent to the original `--dport` option."""

    sample: Optional[int] = field(default=None)
    """If not `None`, enable trace sampling. Equivalent to the original `--sample` option."""


@dataclass
class ProbeEvent(DataclassConversionMixin):

    @dataclass
    class RawProbeEvent(DataclassConversionMixin):
        saddr: int
        sport: int
        daddr: str
        dport: int
        seq: int
        ack: int
        qdisc_timestamp: int
        total_time: int
        qdisc_time: int
        ip_time: int
        tcp_time: int

    @dataclass
    class ParsedProbeEvent(DataclassConversionMixin):
        saddr: str
        sport: int
        daddr: str
        dport: int
        seq: int
        ack: int
        qdisc_timestamp: float
        total_time: float
        qdisc_time: float
        ip_time: float
        tcp_time: float

    raw: RawProbeEvent
    parsed: ParsedProbeEvent

    def __post_init__(self):
        if isinstance(self.raw, dict):
            self.raw = ProbeEvent.RawProbeEvent.from_dict(
                cast(dict[str, Any], self.raw))
        if isinstance(self.parsed, dict):
            self.parsed = ProbeEvent.ParsedProbeEvent.from_dict(
                cast(dict[str, Any], self.parsed))

    @classmethod
    def from_raw_event(cls, raw_event: RawProbeEvent):
        parsed_event = cls.ParsedProbeEvent(
            saddr=inet_ntop(AF_INET, pack('I', raw_event.saddr)),
            sport=raw_event.sport,
            daddr=inet_ntop(AF_NETBEUI, pack('I', raw_event.daddr)),
            dport=raw_event.dport,
            seq=raw_event.seq,
            ack=raw_event.ack,
            qdisc_timestamp=raw_event.qdisc_timestamp / 1000,
            total_time=raw_event.total_time / 1000,
            qdisc_time=raw_event.qdisc_time / 1000,
            ip_time=raw_event.ip_time / 1000,
            tcp_time=raw_event.tcp_time / 1000)
        return cls(raw=raw_event, parsed=parsed_event)


class Probe(BaseProbe):

    _PERF_BUFFER_NAME = 'timestamp_events'

    def __init__(self, event_callback: EventCallback,
                 options: Union[None, dict, ProbeOptions]) -> None:
        super().__init__(event_callback)
        self._options = Probe._convert_options(options)
        self._bpf = Probe._build_bpf(self._options)
        self._bpf[Probe._PERF_BUFFER_NAME].open_perf_buffer(
            self._perf_buffer_callback)
        self._thread: Optional[Thread] = None
        self._lock = Lock()

    def start(self) -> None:

        def run_async():
            while self._thread is not None:
                self._bpf.perf_buffer_poll(200)

        with self._lock:
            if self._thread is not None:
                return

            self._thread = Thread(target=run_async, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self._thread is None:
                return

            thread, self._thread = self._thread, None
            for _ in range(30):
                if not thread.is_alive():
                    return
            raise RuntimeError('Failed to stop')

    def _perf_buffer_callback(self, cpu, data, size):
        event_data = self._bpf[Probe._PERF_BUFFER_NAME].event(data)
        raw_event = ProbeEvent.RawProbeEvent(
            saddr=event_data.saddr,
            sport=event_data.sport,
            daddr=event_data.daddr,
            dport=event_data.dport,
            seq=event_data.seq,
            ack=event_data.ack,
            qdisc_timestamp=event_data.qdisc_timestamp,
            total_time=event_data.total_time,
            qdisc_time=event_data.qdisc_time,
            ip_time=event_data.ip_time,
            tcp_time=event_data.tcp_time)
        event = ProbeEvent.from_raw_event(raw_event)
        return event

    @staticmethod
    def _build_bpf(options: ProbeOptions) -> BPF:
        with open(Path(__file__).parent / 'delay_analysis_out.bpf.c',
                  'r',
                  encoding='utf-8') as fp:
            bpf_text = fp.read()

        if options.sport:
            bpf_text = bpf_text.replace(
                '##FILTER_SPORT##',
                'if (pkt_tuple.sport != %d) { return 0; }' % options.sport)
        else:
            bpf_text = bpf_text.replace('##FILTER_SPORT##',
                                        '/* FILTER_SPORT disabled */')

        if options.dport:
            bpf_text = bpf_text.replace(
                '##FILTER_DPORT##',
                'if (pkt_tuple.dport != %d) { return 0; }' % options.dport)
        else:
            bpf_text = bpf_text.replace('##FILTER_DPORT##',
                                        '/* FILTER_DPORT disabled */')

        if options.sample:
            bpf_text = bpf_text.replace(
                '##SAMPLING##',
                'if (((pkt_tuple.seq + pkt_tuple.ack + skb->len) << (32-%d) >> (32-%d)) != ((0x01 << %d) - 1)) { return 0;}'
                % (options.sample, options.sample, options.sample))
        else:
            bpf_text = bpf_text.replace('##SAMPLING##',
                                        '/* SAMPLING disabled */')

        bpf = BPF(text=bpf_text)
        return bpf

    @staticmethod
    def _convert_options(
            options: Union[None, dict, ProbeOptions]) -> ProbeOptions:
        if options is None:
            return ProbeOptions()
        elif isinstance(options, dict):
            return ProbeOptions.from_dict(options)
        elif isinstance(options, ProbeOptions):
            return options
        else:
            raise RuntimeError(
                'Unrecognized type of options {}'.format(options))
