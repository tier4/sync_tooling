import rclpy
from diagnostic_updater import Updater


class Ros2Adapter:
    def __init__(self, ros_args: list[str]) -> None:
        rclpy.init(args=ros_args)
        self.node = rclpy.create_node("sync_diag_master")  # type: ignore
        self.diag_updater = Updater(self.node, 0)
        self.diag_updater.setHardwareID("none")
