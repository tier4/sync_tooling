from sync_graph import LinuxClockDeviceId, SystemClockId

from linuxptp_monitor.ethtool_harness import CanonicalizedClock


def linuxptp_to_graph_clock_id(
    clock_id: CanonicalizedClock, hostname: str
) -> LinuxClockDeviceId | SystemClockId:
    match clock_id:
        case "CLOCK_REALTIME":
            return SystemClockId(hostname)
        case int():
            return LinuxClockDeviceId(hostname, clock_id)
