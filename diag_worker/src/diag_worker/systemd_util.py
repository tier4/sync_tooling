"""Utilities for interacting with systemd units."""

import re
import shutil
import subprocess


def get_command_line(pid: int) -> list[str]:
    """Read the command line arguments for a process from /proc/[pid]/cmdline.

    Args:
        pid: The process ID.

    Returns:
        List of command line arguments.
    """
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


def _get_systemctl():
    """
    Find the systemctl executable.

    Raises:
        RuntimeError: If systemctl is not found.
    Returns:
        The path to the systemctl executable.
    """
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        raise RuntimeError("Could not find systemctl executable")
    return systemctl


def get_unit_property(unit_name: str, property_name: str) -> str:
    """
    Return the value of a property of a systemd unit.

    Args:
        unit_name: The name of the systemd unit to get the property of.
        property_name: The name of the property to get the value of.

    Raises:
        KeyError: If the property is not found for the unit.

    Returns:
        The value of the property.
    """
    result = subprocess.run(
        [_get_systemctl(), "show", unit_name],
        text=True,
        capture_output=True,
        check=True,
    )

    if m := re.search(f"^{property_name}=(.*?)$", result.stdout, re.MULTILINE):
        return m.group(1)

    raise KeyError(f"Property '{property_name}' was not found for unit '{unit_name}'")


def does_unit_exist(unit_name: str) -> bool:
    """
    Check if a systemd unit is defined and loaded. This does not check if the unit is running.

    Args:
        unit_name: The name of the systemd unit to check.

    Returns:
        True if the unit is defined and loaded, False otherwise.
    """
    if not unit_name.endswith(".service"):
        unit_name = f"{unit_name}.service"

    result = subprocess.run(
        [_get_systemctl(), "list-unit-files", unit_name], capture_output=True
    )

    return result.returncode == 0
