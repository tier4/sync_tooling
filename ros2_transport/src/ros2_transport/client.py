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
