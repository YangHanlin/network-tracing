import sys
from argparse import ArgumentParser, _SubParsersAction
from dataclasses import dataclass
from typing import Any, Union

from network_tracing.cli.api import ApiClient, ApiException
from network_tracing.cli.constants import DEFAULT_PROGRAM_NAME
from network_tracing.cli.models import BaseOptions


@dataclass
class Options(BaseOptions):
    id: str


def configure_subparsers(subparsers: _SubParsersAction):
    parser: ArgumentParser = subparsers.add_parser(
        'stop',
        aliases=['rm', 'remove'],
        help='stop and remove a tracing task')

    parser.add_argument('id',
                        metavar='ID',
                        help='ID of tracing task to stop and remove')


def run(options: Union[dict[str, Any], Options]):
    if isinstance(options, dict):
        options = Options.from_dict(options)

    try:
        ApiClient.get_instance().remove_tracing_task(options.id)
    except ApiException as e:
        print('{}: error: failed to stop and remove task: {}'.format(
            DEFAULT_PROGRAM_NAME,
            e,
        ),
              file=sys.stderr)
        return 1
