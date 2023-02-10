from dataclasses import dataclass, field
from functools import cache
import logging
from pathlib import Path
from socket import AF_INET6, inet_ntop
from threading import Lock, Thread
from time import sleep
from typing import Any, Optional, Union, cast

from bcc import BPF
from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.tracing.probes.models import BaseProbe, EventCallback

logger = logging.getLogger(__name__)


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
        daddr: int
        dport: int
        seq: int
        ack: int
        mac_timestamp: int
        total_time: int
        mac_time: int
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
        mac_timestamp: float
        total_time: float
        mac_time: float
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
            saddr=inet_ntop(AF_INET6, raw_event.saddr),  # type: ignore
            sport=raw_event.sport,
            daddr=inet_ntop(AF_INET6, raw_event.daddr),  # type: ignore
            dport=raw_event.dport,
            seq=raw_event.seq,
            ack=raw_event.ack,
            mac_timestamp=raw_event.mac_timestamp * 1e-9,
            total_time=raw_event.total_time / 1000,
            mac_time=raw_event.mac_time / 1000,
            ip_time=raw_event.ip_time / 1000,
            tcp_time=raw_event.tcp_time / 1000)

        # FIXME: Workaround for circular reference error in JSON serialization
        raw_event.saddr = -1
        raw_event.daddr = -1

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

            for fn_name, event in Probe._get_kprobe_names().items():
                self._bpf.attach_kprobe(fn_name=fn_name, event=event)

            self._thread = Thread(target=run_async, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self._thread is None:
                return

            thread, self._thread = self._thread, None
            for _ in range(30):
                if not thread.is_alive():
                    break
                sleep(1)
            else:
                if thread.is_alive():
                    raise RuntimeError('Failed to stop')

            for fn_name, event in Probe._get_kprobe_names().items():
                self._bpf.detach_kprobe(fn_name=fn_name, event=event)

    def _perf_buffer_callback(self, cpu, data, size):
        event_data = self._bpf[Probe._PERF_BUFFER_NAME].event(data)
        raw_event = ProbeEvent.RawProbeEvent(
            saddr=event_data.saddr,
            sport=event_data.sport,
            daddr=event_data.daddr,
            dport=event_data.dport,
            seq=event_data.seq,
            ack=event_data.ack,
            mac_timestamp=event_data.mac_timestamp,
            total_time=event_data.total_time,
            mac_time=event_data.mac_time,
            ip_time=event_data.ip_time,
            tcp_time=event_data.tcp_time)
        event = ProbeEvent.from_raw_event(raw_event)
        self._submit_event(event)

    @staticmethod
    def _build_bpf(options: ProbeOptions) -> BPF:
        with open(Path(__file__).parent / 'delay_analysis_in_v6.bpf.c',
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

    @cache
    @staticmethod
    def _get_kprobe_names() -> dict[bytes, bytes]:
        return {
            b'on_eth_type_trans': b'eth_type_trans',
            b'on_ip6_rcv_core': b'ip6_rcv_core',
            b'on_tcp_v6_rcv': b'tcp_v6_rcv',
            b'on_skb_copy_datagram_iter': b'skb_copy_datagram_iter',
        }
