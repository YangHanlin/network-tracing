from argparse import ArgumentParser

from network_tracing.cli import actions
from network_tracing.cli.actions.version import AllVersionsAction
from network_tracing.cli.common import (DEFAULT_BASE_URL,
                                        DEFAULT_CONFIG_FILE_PATH)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser()

    parser.register('action', 'all_versions', AllVersionsAction)

    parser.add_argument('-V', '--version', action='all_versions')
    parser.add_argument(
        '-c',
        '--config',
        default=DEFAULT_CONFIG_FILE_PATH,
        metavar='PATH',
        help='path to configuration file; defaults to {}'.format(
            DEFAULT_CONFIG_FILE_PATH))
    parser.add_argument(
        '-b',
        '--base-url',
        default=DEFAULT_BASE_URL,
        metavar='URL',
        help='base URL of API service exposed by the daemon; defaults to {}'.
        format(DEFAULT_BASE_URL))

    subparsers = parser.add_subparsers(metavar='SUBCOMMAND',
                                       help='specify subcommand to execute',
                                       dest='subcommand',
                                       required=True)
    for configure in actions.subparsers_configurers:
        configure(subparsers)

    return parser


def main():
    args = create_parser().parse_args()
    print('Parsed arguments: {}'.format(args))


if __name__ == '__main__':
    main()
