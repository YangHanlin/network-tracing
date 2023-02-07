from dataclasses import dataclass
from queue import Queue
from typing import Any, Union
from network_tracing.common.utilities import DictConversionMixin
from network_tracing.daemon.common import BackgroundTask
from network_tracing.daemon.tracing.probes import probe_factories


@dataclass
class TracingTaskOptions(DictConversionMixin):

    probes: dict[str, Any]


class TracingTask(BackgroundTask):

    def __init__(self, options: TracingTaskOptions) -> None:
        self._event_queue = Queue()
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
                   timeout: Union[float, None] = None) -> Any:
        return self._event_queue.get(block=blocking, timeout=timeout)

    def _bulid_probes(self,
                      probe_spec: dict[str, Any]) -> dict[str, BackgroundTask]:
        probes: dict[str, BackgroundTask] = {}
        for probe_type, probe_options in probe_spec.items():
            probe_factory = probe_factories.get(probe_type, None)
            if probe_factory is None:
                raise RuntimeError(
                    'Cannot find probe with type \'{}\''.format(probe_type))

            def event_callback(event: Any) -> None:
                event.probe_type = probe_type
                self._event_queue.put(event)

            probes[probe_type] = probe_factory(event_callback, probe_options)
        return probes
