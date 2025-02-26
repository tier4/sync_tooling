from sync_graph import LinuxClockDeviceId, SystemClockId

from linuxptp_monitor.ethtool_harness import CanonicalizedClock
from sync_tooling_msgs.clock_id_pb2 import ClockId


def linuxptp_to_graph_clock_id(clock_id: CanonicalizedClock, hostname: str) -> ClockId:
    match clock_id:
        case "CLOCK_REALTIME":
            return ClockId(system_clock_id=SystemClockId(hostname=hostname))
        case int():
            return ClockId(
                linux_clock_device_id=LinuxClockDeviceId(
                    hostname=hostname, clock_device_number=clock_id
                )
            )
