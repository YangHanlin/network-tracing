from argparse import _SubParsersAction
from typing import Callable, Any

from . import events, ls, start, stop, view

SubparsersConfigurer = Callable[[_SubParsersAction], Any]

subparsers_configurers: list[SubparsersConfigurer] = [
    events.configure_subparsers,
    ls.configure_subparsers,
    start.configure_subparsers,
    stop.configure_subparsers,
    view.configure_subparsers,
]
