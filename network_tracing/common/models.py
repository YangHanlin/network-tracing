from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

from network_tracing.common.utilities import DataclassConversionMixin


@dataclass
class TracingEvent(DataclassConversionMixin):
    timestamp: float
    probe: str
    event: Any

    @property
    def time(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp).astimezone()


@dataclass
class TracingTaskEventOptions(DataclassConversionMixin):
    buffer_length: int = field(default=100)


@dataclass
class TracingTaskOptions(DataclassConversionMixin):
    probes: dict[str, Any]
    events: TracingTaskEventOptions = field(
        default_factory=TracingTaskEventOptions)

    def __post_init__(self):
        if isinstance(self.events, dict):
            self.events = TracingTaskEventOptions.from_dict(self.events)


@dataclass
class ErrorResponse(DataclassConversionMixin):
    message: Optional[str] = field(default=None)


@dataclass
class TracingTaskResponse(DataclassConversionMixin):
    id: str
    options: TracingTaskOptions

    def __post_init__(self):
        if isinstance(self.options, dict):
            self.options = TracingTaskOptions.from_dict(self.options)


@dataclass
class IdResponse(DataclassConversionMixin):
    id: str


@dataclass
class DaemonInfoResponse(DataclassConversionMixin):
    name: str
    version: str


CreateTracingTaskRequest = TracingTaskOptions

ListTracingTasksResponse = list[TracingTaskResponse]

GetTracingTaskResponse = TracingTaskResponse

CreateTracingTaskResponse = IdResponse

GetTracingEventsResponse = Iterable[TracingEvent]
