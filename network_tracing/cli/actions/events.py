import logging
from numbers import Integral
import sys
from argparse import ArgumentParser, _SubParsersAction
from copy import deepcopy
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from signal import SIGINT, SIGTERM, signal
from threading import Thread
from typing import Any, Iterable, Optional, Union

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from network_tracing.cli.api import ApiClient
from network_tracing.cli.constants import DEFAULT_PROGRAM_NAME
from network_tracing.cli.models import BaseOptions
from network_tracing.common.models import TracingEvent

logger = logging.getLogger(__name__)

DEFAULT_EVENT_BUFFER_SIZE = 4096


@dataclass(kw_only=True)
class Options(BaseOptions):
    id: str
    actions: list = field(default_factory=list)
    buffer_size: int = field(default=DEFAULT_EVENT_BUFFER_SIZE)
    influxdb_config: Optional[str] = field(default=None)

    def __post_init__(self):
        if not self.actions:
            self.actions = ['print']

        for action in self.actions:
            if action not in VALID_ACTIONS:
                raise Exception('Invalid action \'{}\''.format(action))


class _BaseAction:

    def initialize(self, options: Options) -> None:
        pass

    def handle_event(self, event: TracingEvent) -> None:
        pass

    def close(self) -> None:
        pass


class _PrintAction(_BaseAction):

    def initialize(self, options: Options) -> None:
        print('{:26} {:20} {}'.format('TIME', 'PROBE', 'EVENT'))

    def handle_event(self, event: TracingEvent) -> None:
        time_str = event.time.strftime('%Y-%m-%d %H:%M:%S,%f')
        print('{:26} {:20} {}'.format(time_str, event.probe, event.event))


# TODO: Generalize
class _UploadAction(_BaseAction):

    def initialize(self, options: Options) -> None:
        self._influxdb_client = _UploadAction._build_influxdb_client(
            options.influxdb_config)
        self._write_api = self._influxdb_client.write_api(SYNCHRONOUS)

    def handle_event(self, event: TracingEvent) -> None:
        formatter = _UploadAction._event_formatters.get(event.probe)
        if formatter is None:
            logger.warn('Cannot recognize probe type \'%s\'; ignoring',
                        event.probe)
        else:
            point_or_points = formatter(self, event)
            if not isinstance(point_or_points, Iterable):
                points = [point_or_points]
            else:
                points = point_or_points
            for point in points:
                logger.debug('Uploading record %s', point)
                self._write_api.write(bucket='network_subsystem', record=point)

    def _format_delay_analysis_out(self, event: TracingEvent):
        timestamp: Integral = event.timestamp  # type: ignore
        return Point('delay_analysis_out') \
            .time(timestamp) \
            .field('SADDR', event.event['parsed']['saddr']) \
            .field('SPORT', event.event['parsed']['sport']) \
            .field('DADDR', event.event['parsed']['daddr']) \
            .field('DPORT', event.event['parsed']['dport']) \
            .field('SEQ', event.event['parsed']['seq']) \
            .field('ACK', event.event['parsed']['ack']) \
            .field('TIME_TOTAL', event.event['parsed']['total_time']) \
            .field('TIME_QDisc', event.event['parsed']['qdisc_time']) \
            .field('TIME_IP', event.event['parsed']['ip_time']) \
            .field('TIME_TCP', event.event['parsed']['tcp_time'])

    def _format_delay_analysis_out_v6(self, event: TracingEvent):
        timestamp: Integral = event.timestamp  # type: ignore
        return Point('delay_analysis_out_v6') \
            .time(timestamp) \
            .field('SADDR', event.event['parsed']['saddr']) \
            .field('SPORT', event.event['parsed']['sport']) \
            .field('DADDR', event.event['parsed']['daddr']) \
            .field('DPORT', event.event['parsed']['dport']) \
            .field('SEQ', event.event['parsed']['seq']) \
            .field('ACK', event.event['parsed']['ack']) \
            .field('TIME_TOTAL', event.event['parsed']['total_time']) \
            .field('TIME_QDisc', event.event['parsed']['qdisc_time']) \
            .field('TIME_IP', event.event['parsed']['ip_time']) \
            .field('TIME_TCP', event.event['parsed']['tcp_time'])

    def _format_retsnoop(self, event: TracingEvent):
        timestamp = event.timestamp
        data: dict[str, Any] = deepcopy(event.event)
        data.pop('timestamp')
        data['time_stamp'] = timestamp
        data['PID'] = data.pop('pid')
        data['TID'] = data.pop('tid')
        data['PNAME'] = data.pop('pname')
        data['TNAME'] = data.pop('tname')

        functions = data.pop('functions')
        if not functions:
            return []
        data.update(functions)

        flows = data.pop('flows')

        points: list[Point] = []

        # points.append(
        #     Point.from_dict({
        #         'measurement': 'function_duration',
        #         'time': timestamp,
        #         'fields': data,
        #     }))

        column_name = '{}:{}_{}:{}'.format(
            data['PID'],
            data['TID'],
            data['PNAME'],
            data['TNAME'],
        )
        points.append(
            Point.from_dict({
                'measurement': 'function_duration_bar',
                'time': timestamp,
                'tags': {
                    'column_name': column_name,
                },
                'fields': data,
            }))

        for flow_data in flows:
            flow_data['time_stamp'] = timestamp
            flow_data['SADDR'] = flow_data.pop('saddr')
            flow_data['SPORT'] = flow_data.pop('sport')
            flow_data['DADDR'] = flow_data.pop('daddr')
            flow_data['DPORT'] = flow_data.pop('dport')

            flow_functions = flow_data.pop('functions')
            if not flow_functions:
                continue
            flow_data.update(flow_functions)

            # points.append(
            #     Point.from_dict({
            #         'measurement': 'function_duration_flow',
            #         'time': timestamp,
            #         'fields': flow_data,
            #     }))

            column_name = '{}:{}_{}:{}'.format(
                flow_data['SADDR'],
                flow_data['SPORT'],
                flow_data['DADDR'],
                flow_data['DPORT'],
            )
            points.append(
                Point.from_dict({
                    'measurement': 'function_duration_flow_bar',
                    'time': timestamp,
                    'tags': {
                        'column_name': column_name,
                    },
                    'fields': flow_data,
                }))

        return points

    def _format_runqslower(self, event: TracingEvent):
        timestamp: Integral = event.timestamp  # type: ignore
        # eBPF 获取到的 PID 在用户态看实际是线程 ID（TID）
        return Point('runqueue_delay') \
            .time(timestamp) \
            .field('task', event.event['task']) \
            .field('tid', event.event['pid']) \
            .field('delta_us', event.event['delta_us'])

    _event_formatters = {
        'delay_analysis_out': _format_delay_analysis_out,
        'delay_analysis_out_v6': _format_delay_analysis_out_v6,
        'retsnoop': _format_retsnoop,
        'runqslower': _format_runqslower,
    }

    @staticmethod
    def _build_influxdb_client(
            influxdb_config_path: Optional[str]) -> InfluxDBClient:
        if influxdb_config_path is None:
            default_org = '-'  # to be compatible with InfluxDB 1.8
            return InfluxDBClient('http://localhost:8086', org=default_org)
        elif influxdb_config_path == ':env:':
            return InfluxDBClient.from_env_properties()
        else:
            return InfluxDBClient.from_config_file(influxdb_config_path)


_action_classes: dict[str, type[_BaseAction]] = {
    'print': _PrintAction,
    'upload': _UploadAction,
}

VALID_ACTIONS = _action_classes.keys()


def configure_subparsers(subparsers: _SubParsersAction):
    parser: ArgumentParser = subparsers.add_parser(
        'events',
        help='view events of a tracing task and/or upload to InfluxDB')

    parser.add_argument(
        '-a',
        '--action',
        metavar='ACTION',
        dest='actions',
        choices=VALID_ACTIONS,
        action='append',
        default=[],
        help=
        'action(s) to take for events; can be one of {}. This option can be '
        'specified more than once to perform multiple actions, and if not '
        'specified, defaults to \'print\'.'.format(', '.join(VALID_ACTIONS)))

    parser.add_argument('-u',
                        '--buffer-size',
                        metavar='N',
                        type=int,
                        help='size of event buffer; defaults to {}'.format(
                            DEFAULT_EVENT_BUFFER_SIZE))

    parser.add_argument(
        '-i',
        '--influxdb-config',
        metavar='PATH',
        help=
        'path to configuration file of InfluxDB Client, or use `:env:` to load '
        'config from environment variables. If not specified, a default client '
        'connecting to http://localhost:8086 will be created. See also '
        'https://influxdb-client.readthedocs.io/en/stable/api.html#influxdb_client.InfluxDBClient.from_config_file.'
    )

    parser.add_argument('id',
                        metavar='ID',
                        help='ID of tracing task to view events')


def run(options: Union[dict[str, Any], Options]):
    try:
        if isinstance(options, dict):
            options = Options.from_dict(options)

        events = ApiClient.get_instance().get_tracing_events(options.id)
        event_buffer: Queue[TracingEvent] = Queue(maxsize=options.buffer_size)

        def poll_event():
            dropped = 0
            while True:
                for event in events:
                    try:
                        event_buffer.put_nowait(event)
                        if dropped:
                            logger.warn(
                                'Dropped %d event(s) as the buffer is full',
                                dropped)
                            dropped = 0
                    except Full:
                        dropped += 1

        thread = Thread(target=poll_event, daemon=True)
        thread.start()

        running = [True]

        def handle_signal(sig, stack):
            running[0] = False

        signal(SIGINT, handle_signal)
        signal(SIGTERM, handle_signal)

        actions = [
            action_class() for name, action_class in _action_classes.items()
            if name in options.actions
        ]

        for action in actions:
            action.initialize(options)

        while running[0]:
            try:
                event = event_buffer.get(block=True, timeout=0.5)
                for action in actions:
                    action.handle_event(event)
            except Empty:
                pass

        for action in actions:
            action.close()

    except Exception as e:
        print('{}: error: failed to get events: {}'.format(
            DEFAULT_PROGRAM_NAME,
            e,
        ),
              file=sys.stderr)
        logger.debug('Exception information:', exc_info=e)
        return 1
