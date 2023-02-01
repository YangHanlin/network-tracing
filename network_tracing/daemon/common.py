from abc import abstractmethod
from typing import Protocol


class BackgroundTask(Protocol):

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError
