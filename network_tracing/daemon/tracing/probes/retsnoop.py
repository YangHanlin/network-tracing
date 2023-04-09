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
from typing import IO, Any, Optional, TextIO, Union, cast

from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.tracing.probes.models import (BaseProbe,
                                                          EventCallback)
from network_tracing.daemon.utilities import IPMatcher

logger = logging.getLogger(__name__)

DEFAULT_TRACED_FUNCTIONS = [
    # Key functions
    'lock_sock_nested',
    'sk_stream_alloc_skb',
    'queue_work_on',
    'queue_delayed_work_on',
    'schedule',
    'dev_queue_xmit',
    'dev_hard_start_xmit',
    'tcp_sendmsg',
    'mptcp_write_xmit',
    'full_mesh_create_subflows',
    'mptcp_backlog_rcv',
    'ip_queue_xmit',
    # Other functions
    '_raw_spin_lock',
    '_raw_spin_lock_bh',
    '_raw_spin_unlock_bh',
    '_raw_spin_lock_irq',
    'sk_page_frag_refill',
    'skb_clone',
    'kmem_cache_alloc',
    'kmem_cache_alloc_node',
    '__pskb_copy_fclone',
    '__queue_work',
    'get_work_pool',
    'insert_work',
    'wake_up_process',
    'netdev_pick_tx',
    'xmit_one',
    'ndo_start_xmit',
    'igb_xmit_frame',
    'tcp_sendmsg_locked',
    'tcp_send_mss',
    'tcp_push',
    '__tcp_push_pending_frames',
    'tcp_write_xmit',
    '__tcp_transmit_skb',
    'tcp_event_new_data_sent',
    'tcp_schedule_loss_probe',
    'tcp_cwnd_test',
    'tcp_established_options',
    'tcp_options_write',
    'tcp_select_window',
    'mptcp_current_mss',
    'mptcp_select_size',
    'mptcp_next_segment',
    'mptcp_handle_options',
    '__ip_local_out',
    'ip_output',
    'ip_copy_addrs',
    'ip_finish_output',
    # Previously traced functions
    'raw_spin_*lock',
    'spin_lock',
    'spin_lock_irq',
    'lock_sock',
    'context_switch',
    'queue_work_on',
    'netdev_core_pick_tx',
    'sch_direct_xmit',
    'net_tx_action',
    'sk_stream_alloc_skb',
    'skb_add_data_nocache',
    # 'skb_clone',  # duplicate
    'pskb_copy',
    '__pskb_copy_fclone',
    'skb_copy',
    '__qdisc_run',
    '*sock_sendmsg*',
    # 'tcp_sendmsg*',  # duplicate
    # '*tcp_write_xmit',  # duplicate
    # 'ip_output',  # duplicate
    '__dev_xmit_skb',
]

KEY_TRACED_FUNCTIONS = [
    # Key functions
    'lock_sock_nested',
    'sk_stream_alloc_skb',
    'queue_work_on',
    'queue_delayed_work_on',
    'schedule',
    'dev_queue_xmit',
    'dev_hard_start_xmit',
    'tcp_sendmsg',
    'mptcp_write_xmit',
    'full_mesh_create_subflows',
    'mptcp_backlog_rcv',
    'ip_queue_xmit',
]


@dataclass
class ProbeOptions(DataclassConversionMixin):

    traced_functions: list[str] = field(
        default_factory=lambda: DEFAULT_TRACED_FUNCTIONS)
    """Functions to trace."""

    trace_key_functions_only: bool = field(default=False)
    """Trace key functions only; this option overrides `traced_functions`."""

    ignore: Union[str,
                  list[str]] = field(default_factory=lambda: ['127.0.0.0/8'])
    """Ignore flows whose source address matches any of give IP addresses or ranges (in CIDR notation)."""

    log_path: Optional[str] = field(default=None)
    """If not `None`, copy stdout from `retsnoop` to specified path."""

    def __post_init__(self):
        self._ignore_matcher = IPMatcher(self.ignore)
        if self.trace_key_functions_only:
            self.traced_functions = KEY_TRACED_FUNCTIONS[:]

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

    _BASE_ARGS = [
        Path(__file__).parent / 'retsnoop',
        '-T',
        '-S',
        '-e',
        'mptcp_sendmsg',
    ]

    # FIXME: swapper/3/swapper/3 is parsed into {'tname': 'swapper/3/swapper', 'pname': '3'} instead of {'tname': 'swapper/3', 'pname': 'swapper/3'}
    _RE_HEADER = re.compile(
        r'(?P<timestamp>\d{19}) -> .* TID/PID (?P<tid>\d*)\/(?P<pid>\d*) \((?P<tname>.*)\/(?P<pname>.*)\)',
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
        self._log_file: Optional[TextIO] = None

    def start(self) -> None:
        if self._running:
            return

        with self._lock:
            self._process = self._create_process()
            self._running = True
            if self._options.log_path is not None:
                try:
                    self._log_file = open(self._options.log_path,
                                          'a',
                                          encoding='utf-8')
                except Exception as e:
                    logger.warn(
                        'Encountered an error while opening log file; will not copy stdout of `retsnoop`',
                        exc_info=e)

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

            if self._log_file is not None:
                self._log_file.close()
                self._log_file = None

    def _build_process_args(self) -> list[Union[str, Path]]:
        args = self._BASE_ARGS[:]
        for traced_function in self._options.traced_functions:
            args.extend(['-a', traced_function])
        return args

    def _create_process(self) -> Popen:
        args = self._build_process_args()
        logger.debug('Starting retsnoop with command %s',
                     ' '.join(map(lambda arg: "'{}'".format(arg), args)))

        process = Popen(args, stdout=PIPE, stderr=PIPE, text=True)

        # # Do not block read() calls, as it might cause threads not exiting
        # os.set_blocking(process.stdout.fileno(), False)  # type: ignore
        # os.set_blocking(process.stderr.fileno(), False)  # type: ignore

        return process

    def _parse_process_stdout(self):
        process_stdout: IO[str] = self._process.stdout  # type: ignore
        log_file: Optional[TextIO] = self._log_file

        @dataclass
        class Context:
            event: Optional[ProbeEvent] = field(default=None)
            curr_depth: int = field(default=-1)
            max_depth: int = field(default=-1)
            ignored_count: int = field(default=0)
            non_header_count: int = field(default=0)

            def reset(self) -> None:
                self.event = None
                self.curr_depth = -1
                self.max_depth = -1

        context = Context()

        def handle_header(line: str):
            if context.event is not None:
                return

            if (header := re.match(self._RE_HEADER, line)) is None:
                context.non_header_count += 1
                if context.non_header_count >= 256:
                    logger.debug('Skipped %d line(s)',
                                 context.non_header_count)
                    context.non_header_count = 0
                return

            if context.non_header_count:
                logger.debug('Skipped %d line(s)', context.non_header_count)
                context.non_header_count = 0

            header_fields = header.groupdict()
            for field in ('timestamp', 'pid', 'tid'):
                header_fields[field] = int(header_fields[field])
            context.reset()
            context.event = ProbeEvent.from_dict(header_fields)

        def handle_missing_record(line: str):
            if context.event is None:
                return

            if re.match(self._RE_MISSING_RECORD, line):
                context.event = None
                logger.debug('Dropped an event (missing record)')
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
                context.ignored_count += 1
                if context.ignored_count >= 256:
                    logger.debug(
                        'Dropped %d event(s) (ignored source address)')
                    context.ignored_count = 0
                return

            if context.ignored_count:
                logger.debug('Dropped %d event(s) (ignored source address)',
                             context.ignored_count)
                context.ignored_count = 0

            if function_entry.group('name') == 'mptcp_sendmsg':
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

            if context.curr_depth < 0:  # 避免前面数据丢失，只剩退出的函数
                context.event = None
                logger.debug('Dropped an event (curr_depth < 0)')
                return

            mark, name, time_str = function_exit.group('mark', 'name', 'time')
            time = float(time_str)
            flow_functions = context.event.flows[context.curr_depth].functions
            flow_functions[name] = flow_functions.get(name, 0.0) + time
            process_functions = context.event.functions
            process_functions[name] = flow_functions.get(name, 0.0) + time
            if mark == '←' and name == 'mptcp_sendmsg':
                context.curr_depth -= 1
                if context.curr_depth < -1:  # 应对一次进去多次退出的特殊情况
                    context.event = None
                    logger.debug('Dropped an event (curr_depth < -1)')
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
                line = process_stdout.readline()
                if log_file is not None:
                    log_file.write(line)
                line = line.strip()
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
