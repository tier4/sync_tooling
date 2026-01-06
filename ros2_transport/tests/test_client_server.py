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

import rclpy
from rclpy.task import Future
from ros2_transport.client import Ros2Client
from ros2_transport.server import Ros2Server
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


def test_communication():
    rclpy.init()
    client_node = rclpy.create_node("client_node")  # type: ignore
    server_node = rclpy.create_node("server_node")  # type: ignore
    client = Ros2Client("test_topic", client_node)

    f = Future()
    _ = Ros2Server("test_topic", server_node, lambda x: f.set_result(x))

    client.send(GraphUpdate(source="test_source"))

    rclpy.spin_until_future_complete(server_node, f)
    result: GraphUpdate = f.result()  # type: ignore
    assert isinstance(result, GraphUpdate)
    assert result.source == "test_source"

    rclpy.shutdown()
