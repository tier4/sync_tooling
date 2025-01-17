import re
import shutil
import subprocess
from typing import Literal


def _find_ethtool():
    ethtool = shutil.which("ethtool")
    if ethtool is None:
        raise RuntimeError(
            "`ethtool` has not been found in PATH. Please install `ethtool`."
        )
    return ethtool


CanonicalizedClock = int | Literal["CLOCK_REALTIME"]


def get_canonicalized_clock(identifier: str) -> CanonicalizedClock:
    """Get the canonical identifier of the clock specified by `identifier`

    Args:
        identifier (str): An interface name (e.g. "eth0"), PTP clock path (e.g. "/dev/ptp0") or the string "CLOCK_REALTIME"

    Returns:
        Path | None: The canonicalized identifier. Either a path to a hardware clock or None (representing CLOCK_REALTIME)
    """

    if identifier == "CLOCK_REALTIME":
        return "CLOCK_REALTIME"

    clock_path_re = r"/dev/ptp(\d+)"
    if m := re.fullmatch(clock_path_re, identifier):
        return int(m.group(1))

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

    hw_clock_re = r"PTP Hardware Clock: (?P<clock_id>none|\d+)"
    m = re.search(hw_clock_re, stdout)
    if not m or m["clock_id"] == "none":
        return "CLOCK_REALTIME"

    clock_id = int(m["clock_id"])
    return clock_id
