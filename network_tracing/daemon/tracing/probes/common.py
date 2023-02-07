from typing import Callable, Any
from network_tracing.daemon.common import BackgroundTask

EventCallback = Callable[..., Any]

ProbeFactory = Callable[[EventCallback, Any], BackgroundTask]


class BaseProbe(BackgroundTask):

    def __init__(self, event_callback: EventCallback) -> None:
        self._submit_event = event_callback
