import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from signal import SIGINT
from socket import AF_INET, inet_ntop
from struct import pack
from subprocess import PIPE, Popen
from threading import Lock, Thread
from time import sleep
from typing import IO, Any, Optional, Union, cast

from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.tracing.probes.models import (BaseProbe,
                                                          EventCallback)
from network_tracing.daemon.utilities import IPMatcher

logger = logging.getLogger(__name__)


@dataclass
class ProbeOptions(DataclassConversionMixin):

    ignore: Union[str,
                  list[str]] = field(default_factory=lambda: ['127.0.0.0/8'])
    """Ignore flows whose source address matches any of give IP addresses or ranges (in CIDR notation)."""

    def __post_init__(self):
        self._ignore_matcher = IPMatcher(self.ignore)

    @property
    def ignore_matcher(self):
        return self._ignore_matcher


@dataclass
class FunctionsPerFlow(DataclassConversionMixin):
    saddr: str
    sport: int
    daddr: str
    dport: int
    functions: dict[str, float] = field(default_factory=dict)


@dataclass
class ProbeEvent(DataclassConversionMixin):
    timestamp: int
    tid: int
    pid: int
    tname: str
    pname: str
    functions: dict[str, float] = field(default_factory=dict)
    flows: list[FunctionsPerFlow] = field(default_factory=list)

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
    _RE_MISSING_RECORD = re.compile(r'‼ ... missing.*', re.U)
    _RE_FUNCTION_ENTRY = re.compile(
        r'\s*[→]\s(?P<name>[a-zA-Z_]*)~\d*~\s*=>(?P<saddr>\d*)-(?P<sport>\d*)-(?P<daddr>\d*)-(?P<dport>\d*)#',
        re.U)
    _RE_FUNCTION_EXIT = re.compile(
        r'\s*(?P<mark>[↔←])\s(?P<name>[a-zA-Z_]*)~\d*~\s*\[.*\]\s*~(?P<time>[0-9]*\.[0-9]*)us<=(?P<saddr>\d*)-(?P<sport>\d*)-(?P<daddr>\d*)-(?P<dport>\d*)#',
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
        args = self._ARGS
        logger.debug('Starting retsnoop with command %s',
                     ' '.join(map(lambda arg: "'{}'".format(arg), args)))

        process = Popen(args, stdout=PIPE, stderr=PIPE, text=True)

        # # Do not block read() calls, as it might cause threads not exiting
        # os.set_blocking(process.stdout.fileno(), False)  # type: ignore
        # os.set_blocking(process.stderr.fileno(), False)  # type: ignore

        return process

    def _parse_process_stdout(self):
        process_stdout: IO[str] = self._process.stdout  # type: ignore

        @dataclass
        class Context:
            event: Optional[ProbeEvent] = field(default=None)
            curr_depth: int = field(default=-1)
            max_depth: int = field(default=-1)

        context = Context()

        def handle_header(line: str):
            if context.event is not None:
                return

            if (header := re.match(self._RE_HEADER, line)) is None:
                return

            header_fields = header.groupdict()
            header_fields['timestamp'] = int(header_fields['timestamp'])
            context.event = ProbeEvent.from_dict(header_fields)

        def handle_missing_record(line: str):
            if context.event is None:
                return

            if re.match(self._RE_MISSING_RECORD, line):
                context.event = None
                return

        def handle_function_entry(line: str):
            if context.event is None:
                return

            if (function_entry := re.match(self._RE_FUNCTION_ENTRY,
                                           line)) is None:
                return

            saddr_bytes = pack('I', int(function_entry.group('saddr')))
            if self._options.ignore_matcher.match_ip4_bytes(saddr_bytes):
                context.event = None
                return

            if function_entry.group('name') == '__tcp_transmit_skb':
                sport, daddr_int, dport = map(
                    int, function_entry.group('sport', 'daddr', 'dport'))
                daddr_bytes = pack('I', daddr_int)
                saddr, daddr = map(
                    lambda ip_bytes: inet_ntop(AF_INET, ip_bytes),
                    (saddr_bytes, daddr_bytes))
                flow_data = FunctionsPerFlow(saddr, sport, daddr, dport)
                context.curr_depth += 1
                if context.max_depth < context.curr_depth:
                    context.max_depth = context.curr_depth
                context.event.flows.append(flow_data)

        def handle_function_exit(line: str):
            if context.event is None:
                return

            if (function_exit := re.match(self._RE_FUNCTION_EXIT,
                                          line)) is None:
                return

            if context.curr_depth < 0:
                context.event = None
                return

            mark, name, time_str = function_exit.group('mark', 'name', 'time')
            time = float(time_str)
            flow_functions = context.event.flows[context.curr_depth].functions
            flow_functions[name] = flow_functions.get(name, 0.0) + time
            process_functions = context.event.functions
            process_functions[name] = flow_functions.get(name, 0.0) + time
            if mark == '←' and name == '__tcp_transmit_skb':
                context.curr_depth -= 1
                if context.curr_depth < -1:
                    context.event = None
                    return

        def handle_tail(line: str):
            if context.event is None:
                return

            if re.match(self._RE_TAIL, line):
                self._submit_event(context.event)
                context.event = None
                return

        while self._running:
            try:
                line = process_stdout.readline().strip()
                if not line:
                    continue
                for handler in (handle_header, handle_missing_record,
                                handle_function_entry, handle_function_exit,
                                handle_tail):
                    handler(line)
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
