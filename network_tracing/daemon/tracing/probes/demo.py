from dataclasses import dataclass, field
from threading import Thread
from time import sleep
from datetime import datetime

from network_tracing.common.utilities import DictConversionMixin
from network_tracing.daemon.tracing.probes.common import BaseProbe, EventCallback
from typing import Any, Optional, Union


@dataclass
class ProbeOptions(DictConversionMixin):
    interval: float = field(default=1.0)


@dataclass
class ProbeEvent(DictConversionMixin):
    current_time: str


class Probe(BaseProbe):

    def __init__(self, event_callback: EventCallback,
                 options: Union[ProbeOptions, None, dict[str, Any]]) -> None:
        super().__init__(event_callback)
        if options is None:
            self._options: ProbeOptions = ProbeOptions()
        elif type(options) == dict:
            self._options: ProbeOptions = ProbeOptions.from_dict(
                options)  # type: ignore
        else:
            self._options: ProbeOptions = options  # type: ignore
        self._thread: Optional[Thread] = None
        self._running: bool = False

    def start(self) -> None:

        def run_async():
            while self._running:
                sleep(self._options.interval)
                self._submit_event(
                    ProbeEvent(current_time=datetime.now().strftime('%c')))

        self._running = True
        self._thread = Thread(target=run_async)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._thread = None
