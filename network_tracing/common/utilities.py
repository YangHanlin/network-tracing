from typing import Any


class DictConversionMixin:
    """A mixin for `@dataclass`-decorated classes to convert from and to dictionaries easily."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return (cls(**data))

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__
