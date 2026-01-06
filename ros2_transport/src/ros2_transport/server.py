# Copyright 2025 TIER IV, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Server (ROS 2 subscriber) for graph updates."""

from typing import Callable

from google.protobuf.message import DecodeError
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


class Ros2Server:
    """Server (ROS 2 subscriber) for graph update messages."""

    def __init__(self, topic: str, node: Node, callback: Callable[[GraphUpdate], None]):
        """Initialize the server with a topic, node, and callback."""
        self._callback = callback
        self._subscriber = node.create_subscription(
            UInt8MultiArray, topic, self._on_raw_message, 1000
        )

    def _on_raw_message(self, msg: UInt8MultiArray):
        """Deserialize and dispatch a received message.

        If the message cannot be parsed as a GraphUpdate, it is ignored.

        Args:
            msg: The received ROS 2 message.

        """
        u = GraphUpdate()
        try:
            u.ParseFromString(bytes(msg.data))
        except DecodeError as e:
            print(e)
            return
        self._callback(u)
