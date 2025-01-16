import dataclasses
import json
from typing import Any, Callable, Type
import rclpy
import rclpy.qos
import rclpy.signals
import std_msgs
import std_msgs.msg


class DataclassJsonEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return self.encode_dataclass_(o)
        return super().default(o)

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
        self, node: rclpy.Node, topic: str, qos: rclpy.qos.QoSProfile | int
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
        node: rclpy.Node,
        topic: str,
        qos: rclpy.qos.QoSProfile | int,
        json_callback: Callable[[Any], None],
        error_callback: Callable[[Any], None],
        known_dataclasses: list[Type],
    ) -> None:
        self.subscription_ = node.create_subscription(
            std_msgs.msg.String, topic, self.callback_, qos
        )

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
        return cls(**o)
