from dataclasses import dataclass, field
from time import CLOCK_MONOTONIC, CLOCK_REALTIME, clock_gettime_ns
from typing import Iterable, NoReturn, Optional, Protocol

from network_tracing.daemon.models import BackgroundTask


@dataclass
class KernelSymbol:

    symbol_address: int
    """Address of the kernel symbol."""

    symbol_name: str
    """Name of the kernel symbol."""

    symbol_type: str
    """Type of the kernel symbol as represented in /proc/kallsyms."""

    module_name: Optional[str] = field(default=None)
    """Name of the module from which the kernel symbol comes. `None` if no module name is available."""

    @staticmethod
    def find_all() -> Iterable['KernelSymbol']:
        with open('/proc/kallsyms', 'r') as fp:
            for line in fp:
                segments = line.strip().split(maxsplit=3)
                symbol_address, symbol_type, symbol_name = segments[:3]
                symbol_address = int(symbol_address, 16)
                if len(segments) > 3:
                    module_name = segments[3][1:-1]
                else:
                    module_name = None
                yield KernelSymbol(symbol_address=symbol_address,
                                   symbol_name=symbol_name,
                                   symbol_type=symbol_type,
                                   module_name=module_name)

    @staticmethod
    def find_by_symbol_name(symbol_name: str) -> Optional['KernelSymbol']:
        # TODO: Add cache
        for symbol in KernelSymbol.find_all():
            if symbol.symbol_name == symbol_name:
                return symbol
        return None


class Ktime:
    _offset: Optional[int] = None

    @staticmethod
    def get_offset(use_cache: bool = True) -> int:
        """Get the offset between timestamps of types `CLOCK_REALTIME` and `CLOCK_MONOTONIC` in ns."""

        if not use_cache or Ktime._offset is None:
            offset = -1
            best_delta = -1
            for _ in range(10):
                t1 = clock_gettime_ns(CLOCK_REALTIME)
                t2 = clock_gettime_ns(CLOCK_MONOTONIC)
                t3 = clock_gettime_ns(CLOCK_REALTIME)
                delta = t3 - t1
                ts = (t1 + t3) // 2
                if best_delta == -1 or delta < best_delta:
                    best_delta = delta
                    offset = ts - t2
            Ktime._offset = offset

        return Ktime._offset

    def __new__(cls: type['Ktime']) -> NoReturn:
        raise Exception('No instantiation for this class')


class _Application(Protocol):
    """An interface for `network_tracing.daemon.app.Application` to avoid circular imports."""

    @property
    def tasks(self) -> dict[str, BackgroundTask]:
        raise NotImplementedError


@dataclass
class _GlobalState:
    application: Optional[_Application] = field(default=None)


global_state = _GlobalState()
