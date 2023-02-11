import logging
import sys
from argparse import _SubParsersAction

from network_tracing.cli.api import ApiClient
from network_tracing.cli.constants import DEFAULT_PROGRAM_NAME

logger = logging.getLogger(__name__)


def configure_subparsers(subparsers: _SubParsersAction):
    parser = subparsers.add_parser('ls',
                                   aliases=['list'],
                                   help='list all tracing tasks')


def run(_=None):
    try:
        tracing_tasks = ApiClient.get_instance().list_tracing_tasks()
        print('{:32} {}'.format('ID', 'PROBES'))
        for task in tracing_tasks:
            probes = task.options.probes.keys()
            print('{:32} {} ({})'.format(task.id, ', '.join(probes),
                                         len(probes)))
    except Exception as e:
        logger.debug('Encountered an exception', exc_info=e)
        print('{}: error: failed to list tracing tasks: {}'.format(
            DEFAULT_PROGRAM_NAME,
            e,
        ),
              file=sys.stderr)
        return 1
