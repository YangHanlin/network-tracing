from argparse import _SubParsersAction


def configure_subparsers(subparsers: _SubParsersAction):
    parser = subparsers.add_parser('ls',
                                   aliases=['list'],
                                   help='list all tracing tasks')


def run(options: dict) -> None:
    pass
