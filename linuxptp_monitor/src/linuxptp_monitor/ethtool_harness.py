"""Ethtool integration for clock device discovery."""

import re
import shutil
import subprocess

from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.linux_clock_device_id_pb2 import LinuxClockDeviceId
from sync_tooling_msgs.system_clock_id_pb2 import SystemClockId

from linuxptp_monitor.util import get_hostname


def _find_ethtool():
    """Find ethtool binary in PATH.

    Raise:
        RuntimeError: If ethtool is not found.

    Returns:
        str: Path to ethtool binary.

    """
    ethtool = shutil.which("ethtool")
    if ethtool is None:
        raise RuntimeError(
            "`ethtool` has not been found in PATH. Please install `ethtool`."
        )
    return ethtool


def get_canonicalized_clock(identifier: str) -> ClockId:
    """Get the canonical identifier of the clock specified by `identifier`.

    Args:
        identifier: An interface name (e.g. "eth0"), PTP clock path (e.g. "/dev/ptp0") or the
            string "CLOCK_REALTIME"

    Returns:
        The canonicalized clock identifier.
    """
    hostname = get_hostname()

    def make_system_clock_id():
        return ClockId(system_clock_id=SystemClockId(hostname=hostname))

    def make_ptp_device_clock_id(device_number: int):
        return ClockId(
            linux_clock_device_id=LinuxClockDeviceId(
                hostname=hostname, clock_device_number=device_number
            )
        )

    if identifier == "CLOCK_REALTIME":
        return make_system_clock_id()

    clock_path_re = r"/dev/ptp(?P<device_number>\d+)"
    if m := re.fullmatch(clock_path_re, identifier):
        device_number = int(m["device_number"])
        return make_ptp_device_clock_id(device_number)

    ethtool = _find_ethtool()
    result = subprocess.run(
        [ethtool, "-T", identifier],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    stdout = result.stdout

    hw_clock_re = r"PTP Hardware Clock: (?P<device_number>none|\d+)"
    m = re.search(hw_clock_re, stdout)
    if not m or m["device_number"] == "none":
        return make_system_clock_id()

    device_number = int(m["device_number"])
    return make_ptp_device_clock_id(device_number)
