import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from signal import SIGINT
from subprocess import PIPE, Popen
from threading import Lock, Thread
from time import sleep
from typing import IO, Any, Optional, Union, cast

from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.tracing.probes.models import (BaseProbe,
                                                          EventCallback)

logger = logging.getLogger(__name__)


@dataclass
class ProbeOptions(DataclassConversionMixin):
    pass


@dataclass
class ProbeEvent(DataclassConversionMixin):
    timestamp: int
    tid: int
    pid: int
    tname: str
    pname: str
    functions: dict[str, float] = field(default_factory=dict)

    def __timestamp__(self) -> int:
        return self.timestamp


class Probe(BaseProbe):

    _ARGS = [
        Path(__file__).parent / 'retsnoop',
        '-T',
        '-S',
        '-e',
        '__tcp_transmit_skb',
        '-a',
        'raw_spin_*lock',
        '-a',
        'spin_lock',
        '-a',
        'spin_lock_irq',
        '-a',
        'lock_sock',
        '-a',
        'context_switch',
        '-a',
        'queue_work_on',
        '-a',
        'netdev_core_pick_tx',
        '-a',
        'sch_direct_xmit',
        '-a',
        'net_tx_action',
        '-a',
        'sk_stream_alloc_skb',
        '-a',
        'skb_add_data_nocache',
        '-a',
        'skb_clone',
        '-a',
        'pskb_copy',
        '-a',
        '__pskb_copy_fclone',
        '-a',
        'skb_copy',
        '-a',
        '__qdisc_run',
        '-a',
        '*sock_sendmsg*',
        '-a',
        'tcp_sendmsg*',
        '-a',
        '*tcp_write_xmit',
        '-a',
        'ip_output',
        '-a',
        '__dev_xmit_skb',
        '-a',
        'sch_direct_xmit',
    ]

    _RE_HEADER = re.compile(
        r'(?P<timestamp>\d{19}) -> .* TID/PID (?P<tid>\d*)\/(?P<pid>\d*) \((?P<tname>\w*)\/(?P<pname>\w*)\)',
        re.U)
    _RE_FUNCTION = re.compile(
        r'\s*[↔←]\s(?P<name>[a-z_]*)\s*\[.*\]\s*(?P<time>[0-9]*\.[0-9]*)us',
        re.U)
    _RE_TAIL = re.compile(r'-END-', re.U)

    def __init__(self, event_callback: EventCallback,
                 options: Union[None, dict[str, Any], ProbeOptions]) -> None:
        super().__init__(event_callback)
        self._options = self._convert_options(options)
        self._lock = Lock()
        self._running = False
        self._process: Optional[Popen[str]] = None
        self._stdout_thread: Optional[Thread] = None
        self._stderr_thread: Optional[Thread] = None

    def start(self) -> None:
        if self._running:
            return

        with self._lock:
            self._process = self._create_process()
            self._running = True
            self._stdout_thread = Thread(target=self._parse_process_stdout,
                                         daemon=True)
            self._stdout_thread.start()
            self._stderr_thread = Thread(target=self._parse_process_stderr,
                                         daemon=True)
            self._stderr_thread.start()

    def stop(self) -> None:
        if not self._running:
            return

        with self._lock:
            process = cast(Popen, self._process)
            stdout_thread = cast(Thread, self._stdout_thread)
            stderr_thread = cast(Thread, self._stderr_thread)

            self._running = False
            for _ in range(20):
                if not stdout_thread.is_alive() and not stderr_thread.is_alive(
                ):
                    self._stdout_thread = None
                    self._stderr_thread = None
                    break
                sleep(0.5)
            else:
                logger.warn('Cannot stop threads parsing output; skipping')

            process.send_signal(SIGINT)
            for _ in range(20):
                if process.returncode is not None:
                    self._process = None
                    logger.debug('Process of retsnoop exited with code %d',
                                 process.returncode)
                    break
                sleep(0.5)
            else:
                logger.warn('Cannot stop retsnoop process; killing')
                process.kill()

    def _create_process(self) -> Popen:
        process = Popen(self._ARGS, stdout=PIPE, stderr=PIPE, text=True)

        # # Do not block read() calls, as it might cause threads not exiting
        # os.set_blocking(process.stdout.fileno(), False)  # type: ignore
        # os.set_blocking(process.stderr.fileno(), False)  # type: ignore

        return process

    def _parse_process_stdout(self):
        process_stdout: IO[str] = self._process.stdout  # type: ignore
        event = None
        while self._running:
            try:
                line = process_stdout.readline().strip()
                if not line:
                    continue
                if event is None:
                    header = re.match(self._RE_HEADER, line)
                    if header is not None:
                        header_fields = header.groupdict()
                        header_fields['timestamp'] = int(
                            header_fields['timestamp'])
                        event = ProbeEvent.from_dict(header_fields)
                else:
                    if (function := re.match(self._RE_FUNCTION,
                                             line)) is not None:
                        function_name = function.group('name')
                        function_time = float(function.group('time'))
                        event.functions[function_name] = event.functions.get(
                            function_name, 0.0) + function_time
                    elif re.match(self._RE_TAIL, line) is not None:
                        self._submit_event(event)
                        event = None
            except Exception as e:
                logger.warn(
                    'Encountered an error while parsing stdout from retsnoop',
                    exc_info=e)

    def _parse_process_stderr(self):
        process_stderr: IO[str] = self._process.stderr  # type: ignore
        while self._running:
            line = process_stderr.readline().strip()
            if not line:
                continue
            logger.debug('retsnoop stderr: %s', line)

    @staticmethod
    def _convert_options(
            options: Union[None, dict[str, Any],
                           ProbeOptions]) -> ProbeOptions:
        if options is None:
            return ProbeOptions()
        elif isinstance(options, dict):
            return ProbeOptions.from_dict(options)
        elif isinstance(options, ProbeOptions):
            return options
        else:
            raise Exception('Invalid options {}'.format(options))
