import dataclasses
import json
from types import UnionType
from typing import Any, Callable, Iterable, Type
import typing
import rclpy
import rclpy.qos
import rclpy.node
import rclpy.signals
import std_msgs
import std_msgs.msg


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


class JsonPublisher:
    def __init__(
        self, node: rclpy.node.Node, topic: str, qos: rclpy.qos.QoSProfile | int
    ) -> None:
        self.publisher_ = node.create_publisher(std_msgs.msg.String, topic, qos)

    def publish(self, obj):
        serialized = json.dumps(
            obj,
            cls=DataclassJsonEncoder,
        )
        msg = std_msgs.msg.String()
        msg.data = serialized
        self.publisher_.publish(msg)


class JsonSubscription:
    def __init__(
        self,
        node: rclpy.node.Node,
        topic: str,
        qos: rclpy.qos.QoSProfile | int,
        json_callback: Callable[[Any], None],
        error_callback: Callable[[Any], None],
        known_types: Iterable[Type | UnionType],
    ) -> None:
        self.subscription_ = node.create_subscription(
            std_msgs.msg.String, topic, self.callback_, qos
        )

        known_dataclasses = set()
        for typ in known_types:
            known_dataclasses |= get_dataclasses_transitive(typ)

        self.json_callback_ = json_callback
        self.error_callback_ = error_callback
        self.known_dataclasses_ = {t.__qualname__: t for t in known_dataclasses}

    def callback_(self, msg: std_msgs.msg.String):
        try:
            j = json.loads(msg.data, object_hook=self.object_hook_)
        except InterruptedError as e:
            raise e
        except Exception as e:
            self.error_callback_(e)
        else:
            self.json_callback_(j)

    def object_hook_(self, o: dict[str, Any]):
        if "__dataclass__" in o:
            return self.decode_dataclass_(o)
        return o

    def decode_dataclass_(self, o: dict[str, Any]):
        class_qualname = o["__dataclass__"]
        cls = self.known_dataclasses_[class_qualname]
        del o["__dataclass__"]
        return cls(
            **{k: json.loads(v, object_hook=self.object_hook_) for k, v in o.items()}
        )
