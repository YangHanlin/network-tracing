from argparse import _SubParsersAction, ArgumentParser


def configure_subparsers(subparsers: _SubParsersAction):
    parser: ArgumentParser = subparsers.add_parser(
        'stop',
        aliases=['rm', 'remove'],
        help='stop and remove a tracing task')

    parser.add_argument('id',
                        metavar='ID',
                        help='ID of tracing task to stop and remove')


def run(options: dict) -> None:
    pass
