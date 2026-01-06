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

"""Client (ROS 2 publisher) for graph updates."""

from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


class Ros2Client:
    """Client (ROS 2 publisher) for graph update messages."""

    def __init__(self, topic: str, node: Node):
        """Initialize the client with a topic and node."""
        self._publisher = node.create_publisher(UInt8MultiArray, topic, 10)

    def send(self, obj: GraphUpdate):
        """Serialize and publish a graph update."""
        serialized = obj.SerializeToString()
        msg = UInt8MultiArray()
        msg.data = serialized
        self._publisher.publish(msg)
