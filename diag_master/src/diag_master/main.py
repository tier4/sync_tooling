import socket

from sync_graph import SyncGraph


import rclpy
import rclpy.qos
from ros2_transport import JsonSubscription
from sync_graph import GraphUpdate


class DiagMaster:
    def __init__(self) -> None:
        hostname = socket.gethostname()
        if not hostname:
            raise RuntimeError("Could not determine hostname")

        self.node = rclpy.create_node(hostname, namespace="/sync_diag/master")  # type: ignore
        self.subscription_ = JsonSubscription(
            self.node,
            "/sync_diag/graph_updates",
            10,
            self.json_callback,
            self.error_callback,
            {GraphUpdate},  # type: ignore
        )

        self.sync_graph_ = SyncGraph()

    def run(self):
        rclpy.spin(self.node)

    def error_callback(self, err):
        self.node.get_logger().error(f"Could not parse received graph update: {err}")

    def json_callback(self, j):
        self.sync_graph_.update(j)


def main():
    rclpy.init()

    diag_master = DiagMaster()
    diag_master.run()
