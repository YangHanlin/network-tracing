from dataclasses import dataclass
from queue import Queue
from typing import Any, Callable, Union
from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.common import BackgroundTask
from network_tracing.daemon.tracing.probes import probe_factories


@dataclass
class TracingTaskOptions(DataclassConversionMixin):

    probes: dict[str, Any]


class TracingTask(BackgroundTask):

    def __init__(self, options: TracingTaskOptions) -> None:
        self._event_queue: Queue[tuple[str, Any]] = Queue()
        self._options = options
        self._probes = self._bulid_probes(options.probes)

    @property
    def options(self):
        return self._options

    def start(self) -> None:
        for probe in self._probes.values():
            probe.start()

    def stop(self) -> None:
        for probe in self._probes.values():
            probe.stop()

    def poll_event(self,
                   blocking: bool = False,
                   timeout: Union[float, None] = None):
        return self._event_queue.get(block=blocking, timeout=timeout)

    def _bulid_probes(self,
                      probe_spec: dict[str, Any]) -> dict[str, BackgroundTask]:
        probes: dict[str, BackgroundTask] = {}
        for probe_type, probe_options in probe_spec.items():
            probe_factory = probe_factories.get(probe_type, None)
            if probe_factory is None:
                raise RuntimeError(
                    'Cannot find probe with type \'{}\''.format(probe_type))
            event_callback = self._build_event_callback(probe_type)
            probes[probe_type] = probe_factory(event_callback, probe_options)
        return probes

    def _build_event_callback(self, probe_type: str) -> Callable:
        return lambda event: self._event_queue.put((probe_type, event))
