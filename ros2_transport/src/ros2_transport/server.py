from typing import Callable

from rclpy.node import Node
from std_msgs.msg import String

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

from .codec import lossless_encode


class Ros2Server:
    def __init__(self, topic: str, node: Node, callback: Callable[[GraphUpdate], None]):
        self._callback = callback
        self._subscriber = node.create_subscription(
            String, topic, self._on_raw_message, 10
        )

    def _on_raw_message(self, msg: String):
        u = GraphUpdate()
        u.ParseFromString(lossless_encode(msg.data))
        self._callback(u)
