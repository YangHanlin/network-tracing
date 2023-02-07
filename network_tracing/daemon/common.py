from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Protocol


class BackgroundTask(Protocol):

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


class _Application(Protocol):
    """An interface for `network_tracing.daemon.app.Application` to avoid circular imports."""

    @property
    def tasks(self) -> dict[str, BackgroundTask]:
        raise NotImplementedError


@dataclass
class _GlobalState:
    application: Optional[_Application] = field(default=None)


global_state = _GlobalState()
