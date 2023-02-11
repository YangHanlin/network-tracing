import logging
import sys
from argparse import ArgumentParser, _SubParsersAction
from dataclasses import dataclass, field
from datetime import datetime
from queue import Empty, Queue
from signal import SIGINT, SIGTERM, signal
from threading import Thread
from typing import Any, Union

from network_tracing.cli.api import ApiClient
from network_tracing.cli.constants import DEFAULT_PROGRAM_NAME
from network_tracing.cli.models import BaseOptions
from network_tracing.common.models import TracingEvent

logger = logging.getLogger(__name__)


class _BaseAction:

    def initialize(self) -> None:
        pass

    def handle_event(self, event: TracingEvent) -> None:
        pass

    def close(self) -> None:
        pass


class _PrintAction(_BaseAction):

    def initialize(self) -> None:
        print('{:26} {:20} {}'.format('TIME', 'PROBE', 'EVENT'))

    def handle_event(self, event: TracingEvent) -> None:
        time = datetime.fromtimestamp(event.timestamp)
        time_str = time.strftime('%Y-%m-%d %H:%M:%S,%f')
        print('{:26} {:20} {}'.format(time_str, event.probe, event.event))


class _UploadAction(_BaseAction):

    def initialize(self) -> None:
        logger.warn('Action `upload` has not been implemented yet')


_action_classes: dict[str, type[_BaseAction]] = {
    'print': _PrintAction,
    'upload': _UploadAction,
}

VALID_ACTIONS = _action_classes.keys()


@dataclass
class Options(BaseOptions):
    id: str
    actions: list = field(default_factory=list)

    def __post_init__(self):
        if not self.actions:
            self.actions = ['print']

        for action in self.actions:
            if action not in VALID_ACTIONS:
                raise Exception('Invalid action \'{}\''.format(action))


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

    parser.add_argument('id',
                        metavar='ID',
                        help='ID of tracing task to view events')


def run(options: Union[dict[str, Any], Options]):
    try:
        if isinstance(options, dict):
            options = Options.from_dict(options)

        events = ApiClient.get_instance().get_tracing_events(options.id)
        queue: Queue[TracingEvent] = Queue()

        def poll_event():
            while True:
                for event in events:
                    queue.put(event)

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
            action.initialize()

        while running[0]:
            try:
                event = queue.get(block=True, timeout=0.5)
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
        return 1
