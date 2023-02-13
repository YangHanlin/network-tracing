from collections import deque
from datetime import datetime
from queue import Queue
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from network_tracing.common.models import TracingEvent, TracingTaskOptions
from network_tracing.daemon.models import BackgroundTask
from network_tracing.daemon.tracing.probes import probe_factories
from network_tracing.daemon.utilities import Ktime


class TracingEventPoller:

    def __init__(self, queue: Queue[TracingEvent],
                 close_hook: Optional[Callable[[], Any]]) -> None:
        self._queue = queue
        self._close_hook = close_hook

    def poll_event(self, block: bool = False, timeout: Optional[float] = None):
        """Get an event. Do not call after calling `close()` or exiting from a `with` block."""
        return self._queue.get(block=block, timeout=timeout)

    def close(self):
        if self._close_hook is not None:
            return self._close_hook()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return self.close()


@runtime_checkable
class TimestampAvailable(Protocol):

    def __timestamp__(self) -> int:
        """Return the timestamp as nanoseconds from the UNIX epoch."""
        raise NotImplementedError

@runtime_checkable
class KtimeAvailable(Protocol):

    def __ktime__(self) -> int:
        """Return the value provided by `bpf_get_ktime_ns()`."""
        raise NotImplementedError


class TracingTask(BackgroundTask):

    class _QueueFromDeque(Queue):

        def __init__(self, initial_data: Optional[deque] = None) -> None:
            self._initial_data = initial_data
            super().__init__()

        def _init(self, maxsize: int) -> None:
            if self._initial_data is not None:
                self.queue = self._initial_data.copy()
            else:
                super()._init(maxsize)

    def __init__(self, options: TracingTaskOptions) -> None:
        self._options = options
        self._event_buffer: deque[TracingEvent] = deque(
            maxlen=self._options.events.buffer_length)
        self._event_queues: set[Queue[TracingEvent]] = set()
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

    def get_event_poller(self) -> TracingEventPoller:
        queue = TracingTask._QueueFromDeque(self._event_buffer)
        self._event_queues.add(queue)

        close_hook = lambda: self._event_queues.remove(queue)

        event_poller = TracingEventPoller(queue=queue, close_hook=close_hook)
        return event_poller

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

    def _build_event_callback(self, probe_type: str) -> Callable[[Any], Any]:

        def event_callback(event: Any):
            # Prefer timestamp passed from kernel space
            if isinstance(event, TimestampAvailable):
                timestamp = event.__timestamp__()
            elif isinstance(event, KtimeAvailable):
                timestamp = Ktime.get_offset() + event.__ktime__()
            else:
                timestamp = int(datetime.now().timestamp() * 1e9)

            wrapped_event = TracingEvent(timestamp=timestamp,
                                         probe=probe_type,
                                         event=event)

            self._event_buffer.append(wrapped_event)
            for queue in self._event_queues:
                queue.put(wrapped_event)

        return event_callback
