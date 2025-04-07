import re
import shutil
import subprocess


def get_command_line(pid: int) -> list[str]:
    with open(f"/proc/{pid}/cmdline") as f:
        cmdline = f.read()

    cmdline = cmdline.removesuffix("\0")
    args = cmdline.split("\0")
    return args


def get_unit_pid(unit_name: str) -> int | None:
    """
    For a running systemd unit, return the PID of the main process. Otherwise, return None.

    Args:
        unit_name: The name of the systemd unit to get the PID of.

    Returns:
        The PID of the main process of the unit, or None if the unit is not running.
    """
    pid = get_unit_property(unit_name, "MainPID")
    try:
        pid = int(pid)
    except ValueError:
        return None
    if pid == 0:
        return None
    return pid


def get_systemctl_():
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        raise RuntimeError("Could not find systemctl executable")
    return systemctl


def get_unit_property(unit_name: str, property_name: str) -> str:
    result = subprocess.run(
        [get_systemctl_(), "show", unit_name],
        text=True,
        capture_output=True,
        check=True,
    )

    if m := re.search(f"^{property_name}=(.*?)$", result.stdout, re.MULTILINE):
        return m.group(1)

    raise KeyError(f"Property '{property_name}' was not found for unit '{unit_name}'")


def does_unit_exist(unit_name: str) -> bool:
    if not unit_name.endswith(".service"):
        unit_name = f"{unit_name}.service"

    result = subprocess.run(
        [get_systemctl_(), "list-unit-files", unit_name], capture_output=True
    )

    return result.returncode == 0
