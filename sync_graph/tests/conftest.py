from typing import Literal

import pytest

from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.interface_id_pb2 import InterfaceId
from sync_tooling_msgs.linux_clock_device_id_pb2 import LinuxClockDeviceId
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.ptp_clock_id_pb2 import PtpClockId
from sync_tooling_msgs.sensor_id_pb2 import SensorId
from sync_tooling_msgs.system_clock_id_pb2 import SystemClockId


@pytest.fixture
def sample_clock_aliases() -> (
    dict[Literal["system", "ptp", "sensor", "iface", "device"], ClockId]
):
    return {
        "system": ClockId(system_clock_id=SystemClockId(hostname="sample")),
        "ptp": ClockId(ptp_clock_id=PtpClockId(id="012345.fffe.6789ab")),
        "sensor": ClockId(sensor_id=SensorId(frame_id="my_sensor")),
        "iface": ClockId(
            interface_id=InterfaceId(hostname="sample", interface_name="eno1")
        ),
        "device": ClockId(
            linux_clock_device_id=LinuxClockDeviceId(
                hostname="sample", clock_device_number=0
            )
        ),
    }


@pytest.fixture
def sample_clock(sample_clock_aliases) -> ClockId:
    return sample_clock_aliases["system"]


@pytest.fixture
def nic_clock():
    return ClockId(
        linux_clock_device_id=LinuxClockDeviceId(
            hostname="sample", clock_device_number=3
        )
    )


@pytest.fixture
def nic_port(nic_clock):
    return PortId(clock_id=nic_clock, port_number=1, ptp_domain=1)


@pytest.fixture
def remote_clock():
    return ClockId(ptp_clock_id=PtpClockId(id="010101.fffe.101010"))
