import dataclasses
import json
from types import UnionType
from typing import Any, Callable, Iterable, Type
import typing
import socket
import asyncio


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


class JsonPublisher:
    def __init__(self, peer_name: str, master_ip: str, master_port: int) -> None:
        self.sock_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_.connect((master_ip, master_port))

    def publish(self, obj):
        serialized = json.dumps(
            obj,
            cls=DataclassJsonEncoder,
        )
        self.sock_.send(serialized.encode())


class JsonSubscription:
    def __init__(
        self,
        bind_ip: str,
        bind_port: int,
        json_callback: Callable[[Any], None],
        known_types: Iterable[Type | UnionType],
    ) -> None:
        self.json_callback_ = json_callback

        self.bind_ip_ = bind_ip
        self.bind_port_ = bind_port

        self.json_decoder_ = DataclassJsonDecoder(known_types)

    async def handle_client_(self, reader: asyncio.StreamReader, _):
        request = ""
        while True:
            request += (await reader.read(1024)).decode("utf8")
            try:
                j, end = self.json_decoder_.raw_decode(request)
            except json.JSONDecodeError:
                continue
            else:
                self.json_callback_(j)
                request = request[end:]

    async def listen(self):
        server = await asyncio.start_server(
            self.handle_client_, self.bind_ip_, self.bind_port_
        )
        async with server:
            await server.serve_forever()
