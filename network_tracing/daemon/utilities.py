import logging
from dataclasses import dataclass, field
from functools import cache
from socket import AF_INET, AF_INET6, inet_pton
from time import CLOCK_MONOTONIC, CLOCK_REALTIME, clock_gettime_ns
from typing import Iterable, NoReturn, Optional, Protocol, Union

from network_tracing.daemon.models import BackgroundTask

logger = logging.getLogger(__name__)


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


class IPMatcher:

    def __init__(self, ips_or_cidrs: Union[str, Iterable[str]]) -> None:
        self._ip4_ranges, self._ip6_ranges = self._compile_ranges(ips_or_cidrs)

    def match(self, ip: str) -> bool:
        if self._is_ip6(ip):
            return self.match_ip6_bytes(inet_pton(AF_INET6, ip))
        else:
            return self.match_ip4_bytes(inet_pton(AF_INET, ip))

    def match_ip4_bytes(self, ip_bytes: bytes) -> bool:
        return self._match_bytes(ip_bytes, self._ip4_ranges)

    def match_ip6_bytes(self, ip_bytes: bytes) -> bool:
        return self._match_bytes(ip_bytes, self._ip6_ranges)

    @staticmethod
    def _compile_ranges(
        ips_or_cidrs: Union[str, Iterable[str]]
    ) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
        ip4_range_list: list[tuple[int, int]] = []
        ip6_range_list: list[tuple[int, int]] = []

        if not isinstance(ips_or_cidrs, Iterable):
            ips_or_cidrs = [ips_or_cidrs]

        for ip_or_cidr in ips_or_cidrs:
            ip, block, *dummy = (*ip_or_cidr.split('/', maxsplit=1), None)
            if IPMatcher._is_ip6(ip):  # IPv6
                ip_binary = IPMatcher._binary_from_bytes(
                    inet_pton(AF_INET6, ip))
                if block is None:
                    ip6_range_list.append((ip_binary, ip_binary + 1))
                else:
                    block = int(block)
                    start = ip_binary & ~((0x01 << 128 - block) - 1)
                    end = start + (0x01 << 128 - block)
                    ip6_range_list.append((start, end))
            else:  # IPv4
                ip_binary = IPMatcher._binary_from_bytes(inet_pton(
                    AF_INET, ip))
                if block is None:
                    ip4_range_list.append((ip_binary, ip_binary + 1))
                else:
                    block = int(block)
                    start = ip_binary & ~((0x01 << 32 - block) - 1)
                    end = start + (0x01 << 32 - block)
                    ip4_range_list.append((start, end))

        return tuple(ip4_range_list), tuple(ip6_range_list)

    @staticmethod
    def _is_ip6(ip: str) -> bool:
        return ':' in ip

    @staticmethod
    def _binary_from_bytes(b: bytes) -> int:
        return int.from_bytes(b, byteorder='big', signed=False)

    @staticmethod
    @cache
    def _match_bytes(ip_bytes: bytes, ip_ranges: tuple[tuple[int, int],
                                                       ...]) -> bool:
        ip_binary = IPMatcher._binary_from_bytes(ip_bytes)
        for ip_range in ip_ranges:
            start, end = ip_range
            if ip_binary >= start and ip_binary < end:
                logger.debug(
                    'Found matching range [0x%x, 0x%x) for IP 0x%x (%s)',
                    start, end, ip_binary, ip_bytes)
                return True
        return False


class _Application(Protocol):
    """An interface for `network_tracing.daemon.app.Application` to avoid circular imports."""

    @property
    def tasks(self) -> dict[str, BackgroundTask]:
        raise NotImplementedError


@dataclass
class _GlobalState:
    application: Optional[_Application] = field(default=None)


global_state = _GlobalState()
