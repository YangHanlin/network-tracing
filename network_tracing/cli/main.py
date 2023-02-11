import json
import logging
import logging.config
import sys
from argparse import ArgumentParser, Namespace
from copy import deepcopy
from typing import Any, Union

from network_tracing.cli import actions
from network_tracing.cli.api import ApiClient
from network_tracing.cli.constants import (DEFAULT_BASE_URL,
                                           DEFAULT_CONFIG_FILE_PATH,
                                           DEFAULT_LOGGING_CONFIG,
                                           DEFAULT_LOGGING_LEVEL,
                                           DEFAULT_PROGRAM_NAME)
from network_tracing.cli.models import BaseOptions

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)


def main():
    args = create_parser().parse_args()
    options_dict = build_options_dict(args)
    run(options_dict)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(prog=DEFAULT_PROGRAM_NAME)

    _configure_base_options(parser)
    _configure_subparsers(parser)

    return parser


def build_options_dict(args: Namespace) -> dict[str, Any]:
    commandline_options = vars(args)

    if commandline_options.get('version', None):
        commandline_options['subcommand'] = 'version'

    if commandline_options.get('subcommand', None) is None:
        print('{}: error: missing subcommand; use -h option for help'.format(
            DEFAULT_PROGRAM_NAME),
              file=sys.stderr)
        sys.exit(1)

    if commandline_options.get('config', None) is None:
        commandline_options['config'] = DEFAULT_CONFIG_FILE_PATH
    config_file_path = commandline_options['config']

    try:
        with open(config_file_path, 'r', encoding='utf-8') as fp:
            config_file_options = json.load(fp)
    except:
        config_file_options = {}

    options = {}
    options.update(config_file_options)
    options.update(
        {k: v
         for k, v in commandline_options.items() if v is not None})

    return options


def run(options: Union[dict[str, Any], BaseOptions]) -> None:
    if isinstance(options, dict):
        options_dict = options
        options = BaseOptions.from_dict(options)
    else:
        options_dict = options.to_dict()

    _configure_logging(options.logging_level)
    _configure_api(options.base_url)
    _dispatch_subcommand(options.subcommand, options_dict)


def _configure_base_options(parser: ArgumentParser) -> None:
    parser.add_argument('-V',
                        '--version',
                        action='store_true',
                        help='show version numbers and exit')

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
                                       required=False)

    for configure in actions.subparsers_configurers:
        configure(subparsers)


def _configure_logging(logging_level: str) -> None:
    logging_config = deepcopy(DEFAULT_LOGGING_CONFIG)
    logging_config['root']['level'] = logging_level
    logging_config['disable_existing_loggers'] = False
    logging.config.dictConfig(logging_config)


def _configure_api(base_url: str) -> None:
    ApiClient.initialize(base_url=base_url)


def _dispatch_subcommand(subcommand: str, payload: Any) -> None:
    actions.subcommand_handlers[subcommand](payload)


if __name__ == '__main__':
    main()
