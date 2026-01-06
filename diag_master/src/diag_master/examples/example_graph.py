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

from pathlib import Path

import yaml
from sync_graph.sync_graph import SyncGraph
from sync_graph.yaml import to_sync_graph_args
from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.linux_clock_device_id_pb2 import LinuxClockDeviceId
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.self_reported_clock_state_update_pb2 import (
    SelfReportedClockStateUpdate,
)
from sync_tooling_msgs.sensor_id_pb2 import SensorId
from sync_tooling_msgs.servo_state_pb2 import ServoState
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState
from sync_tooling_msgs.system_clock_id_pb2 import SystemClockId

CONFIG_FILE = Path(__file__).parent.parent.parent.parent / "config" / "example.yml"


main_sys = ClockId(system_clock_id=SystemClockId(hostname="main-ecu"))
other_sys = ClockId(system_clock_id=SystemClockId(hostname="other-ecu"))

main_ptp0 = ClockId(
    linux_clock_device_id=LinuxClockDeviceId(hostname="main-ecu", clock_device_number=0)
)
main_port0 = PortId(clock_id=main_ptp0, port_number=0, ptp_domain=0)

main_ptp1 = ClockId(
    linux_clock_device_id=LinuxClockDeviceId(hostname="main-ecu", clock_device_number=1)
)
other_ptp0 = ClockId(
    linux_clock_device_id=LinuxClockDeviceId(
        hostname="other-ecu", clock_device_number=0
    )
)

lidar_left = ClockId(sensor_id=SensorId(frame_id="lidar/left"))
lidar_right = ClockId(sensor_id=SensorId(frame_id="lidar/right"))
radar_front = ClockId(sensor_id=SensorId(frame_id="radar/front"))

GRAPH_UPDATES = [
    GraphUpdate(
        self_reported_clock_state_update=SelfReportedClockStateUpdate(
            clock_id=lidar_left, state=SelfReportedClockStateUpdate.State.LOCKED
        )
    ),
    GraphUpdate(
        self_reported_clock_state_update=SelfReportedClockStateUpdate(
            clock_id=lidar_right, state=SelfReportedClockStateUpdate.State.TRACKING
        )
    ),
    GraphUpdate(
        self_reported_clock_state_update=SelfReportedClockStateUpdate(
            clock_id=radar_front, state=SelfReportedClockStateUpdate.State.LOCKED
        )
    ),
    GraphUpdate(
        clock_diff_measurement=ClockDiffMeasurement(
            src=main_sys,
            dst=lidar_left,
            diff_ns=200000,
        )
    ),
    GraphUpdate(
        clock_diff_measurement=ClockDiffMeasurement(
            src=main_sys,
            dst=lidar_right,
            diff_ns=1100000,
        )
    ),
    GraphUpdate(
        clock_diff_measurement=ClockDiffMeasurement(
            src=main_sys,
            dst=radar_front,
            diff_ns=180000,
        )
    ),
    GraphUpdate(
        ptp_parent_update=PtpParentUpdate(clock_id=other_ptp0, parent=main_port0)
    ),
    GraphUpdate(
        clock_master_update=ClockMasterUpdate(
            clock_id=other_ptp0, master=main_ptp0, master_offset_ns=20000
        )
    ),
    GraphUpdate(
        phc2sys_update=Phc2SysUpdate(
            src=main_sys,
            dst=main_ptp0,
            clock_state=SlaveClockState(
                servo_state=ServoState.SERVO_LOCKED, offset_ns=3000, delay_ns=2
            ),
        )
    ),
    GraphUpdate(
        phc2sys_update=Phc2SysUpdate(
            src=main_sys,
            dst=main_ptp1,
            clock_state=SlaveClockState(
                servo_state=ServoState.SERVO_LOCKED, offset_ns=2500, delay_ns=1
            ),
        )
    ),
    GraphUpdate(
        phc2sys_update=Phc2SysUpdate(
            src=other_ptp0,
            dst=other_sys,
            clock_state=SlaveClockState(
                servo_state=ServoState.SERVO_LOCKED, offset_ns=120000, delay_ns=4
            ),
        )
    ),
]


def generate_graph() -> SyncGraph:
    yaml_dict = yaml.safe_load(CONFIG_FILE.read_text())
    config, reference_graph = to_sync_graph_args(yaml_dict)

    sg = SyncGraph(config, reference_graph)
    for update in GRAPH_UPDATES:
        sg.update(update)
    return sg
