from argparse import _SubParsersAction
from typing import Any, Callable

from . import events, ls, start, stop, version, view

SubparsersConfigurer = Callable[[_SubParsersAction], Any]
SubcommandHandler = Callable[[Any], Any]

subparsers_configurers: list[SubparsersConfigurer] = [
    events.configure_subparsers,
    ls.configure_subparsers,
    start.configure_subparsers,
    stop.configure_subparsers,
    view.configure_subparsers,
]

subcommand_handlers = {
    'events': events.run,
    'ls': ls.run,
    'list': ls.run,
    'start': start.run,
    'create': start.run,
    'stop': stop.run,
    'rm': stop.run,
    'remove': stop.run,
    'version': version.run,
    'view': view.run,
}
