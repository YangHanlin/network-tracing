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
        'view', help='view the details of a tracing task')

    parser.add_argument('id', metavar='ID', help='ID of tracing task to view')


def run(options: Union[dict[str, Any], Options]):
    if isinstance(options, dict):
        options = Options.from_dict(options)

    try:
        tracing_task = ApiClient.get_instance().get_tracing_task(options.id)
    except ApiException as e:
        print('{}: error: failed to retrieve information: {}'.format(
            DEFAULT_PROGRAM_NAME,
            e,
        ),
              file=sys.stderr)
        return 1

    print(f'ID: {tracing_task.id}')
    print(f'Event buffer length: {tracing_task.options.events.buffer_length}')
    print(f'Probes ({len(tracing_task.options.probes)}):')
    for probe_type, probe_options in tracing_task.options.probes.items():
        print(f'  {probe_type}: {probe_options}')
