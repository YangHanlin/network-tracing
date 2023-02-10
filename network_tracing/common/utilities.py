from dataclasses import fields, is_dataclass, asdict
import json
from typing import Any


class DataclassConversionMixin:
    """A mixin for `@dataclass`-decorated classes (or similar classes) to convert from and to various formats easily."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        field_names = set(map(lambda f: f.name, fields(cls)))
        filtered_data = {
            key: value
            for key, value in data.items() if key in field_names
        }

        return cls(**filtered_data)

    def to_dict(self) -> dict[str, Any]:
        if is_dataclass(self):
            return asdict(self)
        else:
            return self.__dict__

    @classmethod
    def from_json(cls, data: str):
        args = json.loads(data)
        return cls.from_dict(args)

    def to_json(self: Any) -> str:
        if isinstance(self, DataclassConversionMixin):
            encoder_class = self._JsonEncoder
        else:
            encoder_class = DataclassConversionMixin._JsonEncoder
        return json.dumps(self, cls=encoder_class)

    class _JsonEncoder(json.JSONEncoder):

        def default(self, o: Any) -> Any:
            if isinstance(o, DataclassConversionMixin):
                o = o.to_dict()
            return o
