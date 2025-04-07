from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


class Ros2Client:
    def __init__(self, topic: str, node: Node):
        self._publisher = node.create_publisher(UInt8MultiArray, topic, 10)

    def send(self, obj: GraphUpdate):
        serialized = obj.SerializeToString()
        msg = UInt8MultiArray()
        msg.data = serialized
        self._publisher.publish(msg)
