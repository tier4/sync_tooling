from rclpy.node import Node
from std_msgs.msg import String

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

from .codec import lossless_decode


class Ros2Client:
    def __init__(self, topic: str, node: Node):
        self._publisher = node.create_publisher(String, topic, 10)

    def send(self, obj: GraphUpdate):
        serialized = obj.SerializeToString()
        msg = String()
        msg.data = lossless_decode(serialized)
        self._publisher.publish(msg)
