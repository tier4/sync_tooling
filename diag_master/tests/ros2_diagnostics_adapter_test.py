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

import pytest
from diag_master.ros2_diagnostics_adapter import _diagnostic_clock_name
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.interface_id_pb2 import InterfaceId
from sync_tooling_msgs.linux_clock_device_id_pb2 import LinuxClockDeviceId
from sync_tooling_msgs.ptp_clock_id_pb2 import PtpClockId
from sync_tooling_msgs.sensor_id_pb2 import SensorId
from sync_tooling_msgs.system_clock_id_pb2 import SystemClockId


@pytest.mark.parametrize(
    ("clock_id", "diagnostic_name"),
    [
        pytest.param(
            ClockId(system_clock_id=SystemClockId(hostname="main")),
            "main_sys",
            id="system",
        ),
        pytest.param(
            ClockId(
                linux_clock_device_id=LinuxClockDeviceId(
                    hostname="main", clock_device_number=0
                )
            ),
            "main_ptp0",
            id="linux_clock",
        ),
        pytest.param(
            ClockId(interface_id=InterfaceId(hostname="main", interface_name="eth0")),
            "main_eth0",
            id="interface",
        ),
        pytest.param(
            ClockId(system_clock_id=SystemClockId(hostname="sample-bus")),
            "sample-bus_sys",
            id="hyphenated_hostname",
        ),
        pytest.param(
            ClockId(sensor_id=SensorId(frame_id="front/camera")),
            "sensor@front/camera",
            id="sensor",
        ),
        pytest.param(
            ClockId(ptp_clock_id=PtpClockId(id="12af56.fffe.65EC21")),
            "12af56_fffe_65EC21",
            id="ptp",
        ),
    ],
)
def test_diagnostic_clock_name(clock_id: ClockId, diagnostic_name: str):
    assert _diagnostic_clock_name(clock_id) == diagnostic_name
