from argparse import SUPPRESS, Action


def _show_versions():
    print('Not implemented yet')


class AllVersionsAction(Action):

    def __init__(self,
                 option_strings,
                 dest=SUPPRESS,
                 default=SUPPRESS,
                 help='show version numbers and exit'):
        super(AllVersionsAction, self).__init__(option_strings=option_strings,
                                                dest=dest,
                                                default=default,
                                                nargs=0,
                                                help=help)

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        _show_versions()
        parser.exit()
