import logging
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from threading import Lock, Thread
from time import sleep
from typing import Optional, Union

from bcc import BPF

from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.tracing.probes.models import (BaseProbe,
                                                          EventCallback)

logger = logging.getLogger(__name__)


@dataclass
class ProbeOptions(DataclassConversionMixin):
    min_us: int = field(default=200)
    """Minimum run queue latency to trace, in us (default 200)."""

    pid: Optional[int] = field(default=None)
    """Trace this PID only. Equivalent to the previous `--pid` option."""

    tid: Optional[int] = field(default=None)
    """Trace this TID only. Equivalent to the previous `--tid` option."""


@dataclass
class ProbeEvent(DataclassConversionMixin):
    pid: int
    tgid: int
    prev_pid: int
    task: str
    prev_task: str
    delta_us: int


class Probe(BaseProbe):

    _PERF_BUFFER_NAME = 'events'

    def __init__(self, event_callback: EventCallback,
                 options: Union[dict, None, ProbeOptions]) -> None:
        super().__init__(event_callback)
        self._options = self._convert_options(options)
        self._bpf = self._build_bpf(self._options)
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
        event = ProbeEvent(pid=event_data.pid,
                           tgid=event_data.tgid,
                           prev_pid=event_data.prev_pid,
                           task=event_data.task.decode(),
                           prev_task=event_data.prev_task.decode(),
                           delta_us=event_data.delta_us)
        self._submit_event(event)

    @staticmethod
    def _build_bpf(options: ProbeOptions) -> BPF:
        bpf_text = Probe._load_bpf_text()
        bpf_text = Probe._alter_bpf_text(bpf_text, options)
        return BPF(text=bpf_text)

    @staticmethod
    def _load_bpf_text() -> str:
        source_directory = Path(__file__).parent
        source_file = source_directory / 'runqslower.raw_tracepoint.bpf.c' \
            if Probe._use_raw_tracepoint() \
                  else source_directory / 'runqslower.kprobe.bpf.c'
        with open(source_file, 'r', encoding='utf-8') as fp:
            return fp.read()

    @staticmethod
    def _alter_bpf_text(bpf_text: str, options: ProbeOptions) -> str:
        if BPF.kernel_struct_has_field(b'task_struct', b'__state') == 1:
            bpf_text = bpf_text.replace('STATE_FIELD', '__state')
        else:
            bpf_text = bpf_text.replace('STATE_FIELD', 'state')

        if options.min_us == 0:
            bpf_text = bpf_text.replace('FILTER_US', '0')
        else:
            bpf_text = bpf_text.replace('FILTER_US',
                                        'delta_us <= %s' % str(options.min_us))

        if options.tid:
            bpf_text = bpf_text.replace('FILTER_PID',
                                        'pid != %s' % options.tid)
        else:
            bpf_text = bpf_text.replace('FILTER_PID', '0')

        if options.pid:
            bpf_text = bpf_text.replace('FILTER_TGID',
                                        'tgid != %s' % options.pid)
        else:
            bpf_text = bpf_text.replace('FILTER_TGID', '0')

        return bpf_text

    @staticmethod
    def _convert_options(
            options: Union[dict, None, ProbeOptions]) -> ProbeOptions:
        if options is None:
            return ProbeOptions()
        elif isinstance(options, dict):
            return ProbeOptions.from_dict(options)  # type: ignore
        elif isinstance(options, ProbeOptions):
            return options
        else:
            raise RuntimeError(
                'Unrecognized type of options {}'.format(options))

    @cache
    @staticmethod
    def _use_raw_tracepoint() -> bool:
        return BPF.support_raw_tracepoint()

    @cache
    @staticmethod
    def _get_kprobe_names() -> dict[bytes, bytes]:
        if Probe._use_raw_tracepoint():
            return {}

        logger.debug(
            'Raw tracepoints are not supported; using kprobes as an alternative'
        )

        finish_task_switch_events = BPF.get_kprobe_functions(
            event_re=r"^finish_task_switch$|^finish_task_switch\.isra\.\d$")
        return {
            b'trace_ttwu_do_wakeup': b'ttwu_do_wakeup',
            b'trace_wake_up_new_task': b'wake_up_new_task',
            **{b'trace_run': event
               for event in finish_task_switch_events},
        }
