import logging
import logging.config
from argparse import ArgumentParser

from network_tracing.cli import actions
from network_tracing.cli.actions.version import AllVersionsAction
from network_tracing.cli.constants import (DEFAULT_BASE_URL,
                                           DEFAULT_CONFIG_FILE_PATH,
                                           DEFAULT_LOGGING_CONFIG,
                                           DEFAULT_LOGGING_LEVEL)

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser()
    _configure_common_options(parser)
    _configure_subparsers(parser)
    return parser


def main():
    args = create_parser().parse_args()
    print('Parsed arguments: {}'.format(args))


def _configure_common_options(parser: ArgumentParser) -> None:
    parser.register('action', 'all_versions', AllVersionsAction)
    parser.add_argument('-V', '--version', action='all_versions')

    parser.add_argument(
        '-c',
        '--config',
        metavar='PATH',
        help='path to configuration file; defaults to {}'.format(
            DEFAULT_CONFIG_FILE_PATH))

    parser.add_argument(
        '-b',
        '--base-url',
        metavar='URL',
        help='base URL of API service exposed by the daemon; defaults to {}'.
        format(DEFAULT_BASE_URL))

    try:
        allowed_logging_levels = logging._nameToLevel.keys()
    except:
        allowed_logging_levels = ['<failed to get available logging levels>']
    parser.add_argument(
        '-l',
        '--logging-level',
        metavar='LEVEL',
        choices=allowed_logging_levels,
        help=
        'name of logging level; defaults to {}. This option can be one of {}.'.
        format(DEFAULT_LOGGING_LEVEL, ', '.join(allowed_logging_levels)))


def _configure_subparsers(parser: ArgumentParser) -> None:
    subparsers = parser.add_subparsers(metavar='SUBCOMMAND',
                                       help='specify subcommand to execute',
                                       dest='subcommand',
                                       required=True)

    for configure in actions.subparsers_configurers:
        configure(subparsers)


if __name__ == '__main__':
    main()
