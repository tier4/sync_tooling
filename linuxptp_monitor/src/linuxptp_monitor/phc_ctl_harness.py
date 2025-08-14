import re
import shutil
import subprocess
import time

from linuxptp_monitor.util import get_hostname, linux_clock_device_id_to_path
from sync_tooling_msgs.clock_id_pb2 import ClockId


def _find_phc_ctl():
    phc_ctl = shutil.which("phc_ctl")
    if phc_ctl is None:
        raise RuntimeError(
            "`phc_ctl` has not been found in PATH. Please install `linuxptp`."
        )
    return phc_ctl


def _get_phc_time_ns(clock_name: str) -> int:
    phc_ctl = _find_phc_ctl()
    result = subprocess.run(
        [phc_ctl, "-q", clock_name, "get"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    if result.stderr:
        msg = f"Error while querying PHC time: {result.stderr.strip()}"
        raise RuntimeError(msg)

    time_re = r"clock time is (?P<time_s>\d+)\.(?P<time_ns>\d{9})"

    match = re.search(time_re, result.stdout)
    if not match:
        msg = (
            f"Unexpected output format while querying PHC time: {result.stdout.strip()}"
        )
        raise RuntimeError(msg)

    time_s = int(match.group("time_s"))
    time_ns = int(match.group("time_ns"))
    return time_s * 1_000_000_000 + time_ns


def get_time_ns(local_clock: ClockId) -> int:
    """Get the time of local hardware or system clock specified by `local_clock`

    Args:
        local_clock (ClockId): The local clock identifier.

    Returns:
        int: The time of the hardware clock in nanoseconds.
    """

    def _ensure_hostname_is_local(hostname: str):
        local_host = get_hostname()
        if hostname != get_hostname():
            msg = f"Clock host '{hostname}' is not local to this host ('{local_host}')."
            raise ValueError(msg)

    match local_clock.WhichOneof("id"):
        case "linux_clock_device_id":
            _ensure_hostname_is_local(local_clock.linux_clock_device_id.hostname)
            path = linux_clock_device_id_to_path(local_clock.linux_clock_device_id)
            return _get_phc_time_ns(path)
        case "system_clock_id":
            _ensure_hostname_is_local(local_clock.system_clock_id.hostname)
            return time.time_ns()
        case "interface_id":
            _ensure_hostname_is_local(local_clock.interface_id.hostname)
            return _get_phc_time_ns(local_clock.interface_id.interface_name)
        case _:
            raise ValueError(
                "The given clock must be a local hardware clock or system clock."
            )
