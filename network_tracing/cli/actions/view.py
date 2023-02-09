from argparse import _SubParsersAction, ArgumentParser


def configure_subparsers(subparsers: _SubParsersAction):
    parser: ArgumentParser = subparsers.add_parser(
        'view', help='view the details of a tracing task')

    parser.add_argument('id', metavar='ID', help='ID of tracing task to view')
