from typing import Callable

from google.protobuf.message import DecodeError
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


class Ros2Server:
    def __init__(self, topic: str, node: Node, callback: Callable[[GraphUpdate], None]):
        self._callback = callback
        self._subscriber = node.create_subscription(
            UInt8MultiArray, topic, self._on_raw_message, 10
        )

    def _on_raw_message(self, msg: UInt8MultiArray):
        u = GraphUpdate()
        try:
            u.ParseFromString(bytes(msg.data))
        except DecodeError as e:
            print(e)
            return
        self._callback(u)
