from argparse import _SubParsersAction, ArgumentParser


def configure_subparsers(subparsers: _SubParsersAction):
    parser: ArgumentParser = subparsers.add_parser(
        'start', aliases=['create'], help='create and start a tracing task')

    parser.add_argument(
        'options',
        metavar='OPTIONS',
        action='append',
        help='options of the task being created, in the format KEY=VALUE')


def run(options: dict) -> None:
    pass
