from dataclasses import dataclass, field
from typing import Callable, Any, Optional
from network_tracing.common.utilities import DictConversionMixin
from network_tracing.daemon.common import BackgroundTask

EventCallback = Callable[..., Any]

ProbeFactory = Callable[[EventCallback, Any], BackgroundTask]


class BaseProbe(BackgroundTask):

    def __init__(self, event_callback: EventCallback) -> None:
        self._submit_event = event_callback
