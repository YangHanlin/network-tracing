from argparse import _SubParsersAction, ArgumentParser

_ALLOWED_ACTIONS = {'view', 'upload'}


def configure_subparsers(subparsers: _SubParsersAction):
    parser: ArgumentParser = subparsers.add_parser(
        'events',
        help='view events of a tracing task and/or upload to InfluxDB')

    parser.add_argument(
        '-a',
        '--action',
        metavar='ACTION',
        dest='actions',
        choices=_ALLOWED_ACTIONS,
        action='append',
        default=[],
        help=
        'action(s) to take for events; can be one of {}. This option can be '
        'specified more than once to perform multiple actions, and if not '
        'specified, defaults to \'view\'.'.format(', '.join(_ALLOWED_ACTIONS)))

    parser.add_argument('id',
                        metavar='ID',
                        help='ID of tracing task to view events')


def run(options: dict) -> None:
    pass
