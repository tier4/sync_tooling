import dataclasses
import json
from types import UnionType
from typing import Any, Iterable, Type
import typing

import requests


def get_dataclasses_transitive(typ: Type | UnionType | str) -> set[Type | UnionType]:
    if isinstance(typ, str):
        raise ValueError("Cannot deal with string type annotations yet")

    types = set()
    for arg in typing.get_args(typ):
        types |= get_dataclasses_transitive(arg)

    if dataclasses.is_dataclass(typ):
        types |= {typ}
        for f in dataclasses.fields(typ):
            types |= get_dataclasses_transitive(f.type)

    return types  # type: ignore


class DataclassJsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, set):
            return self.default(list(o))
        if dataclasses.is_dataclass(o):
            return self.encode_dataclass_(o)
        return super().encode(o)

    def encode_dataclass_(self, o):
        if not dataclasses.is_dataclass(o):
            raise TypeError()

        return {
            "__dataclass__": o.__class__.__qualname__,  # type: ignore
            **{
                field.name: self.default(getattr(o, field.name))
                for field in dataclasses.fields(o)
            },
        }


class DataclassJsonDecoder(json.JSONDecoder):
    def __init__(self, known_types: Iterable[Type | UnionType]) -> None:
        super().__init__(object_hook=self.object_hook_)

        known_dataclasses = set()
        for typ in known_types:
            known_dataclasses |= get_dataclasses_transitive(typ)
        self.known_dataclasses_ = {t.__qualname__: t for t in known_dataclasses}

    def object_hook_(self, o: dict[str, Any]):
        if "__dataclass__" in o:
            return self.decode_dataclass_(o)
        return o

    def decode_dataclass_(self, o: dict[str, Any]):
        class_qualname = o["__dataclass__"]
        cls = self.known_dataclasses_[class_qualname]
        del o["__dataclass__"]
        return cls(
            **{
                k: self.decode(v) if not dataclasses.is_dataclass(v) else v
                for k, v in o.items()
            }
        )


class HttpClient:
    def __init__(self, endpoint_url: str) -> None:
        self.session_ = requests.Session()
        self.endpoint_ = endpoint_url

    def send(self, obj):
        serialized = json.dumps(
            obj,
            cls=DataclassJsonEncoder,
        )

        response = self.session_.post(
            self.endpoint_, serialized, headers={"Content-Type": "application/json"}
        )

        if response.status_code != 200:
            raise requests.HTTPError(response=response)
