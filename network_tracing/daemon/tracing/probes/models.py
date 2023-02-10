from typing import Any, Callable

from network_tracing.daemon.models import BackgroundTask

EventCallback = Callable[..., Any]

ProbeFactory = Callable[[EventCallback, Any], BackgroundTask]


class BaseProbe(BackgroundTask):

    def __init__(self, event_callback: EventCallback) -> None:
        self._submit_event = event_callback
