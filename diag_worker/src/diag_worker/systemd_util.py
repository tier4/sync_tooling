import shutil
import subprocess


def get_command_line(pid: int) -> list[str]:
    with open(f"/proc/{pid}/cmdline") as f:
        cmdline = f.read()

    cmdline = cmdline.removesuffix("\0")
    args = cmdline.split("\0")
    return args


def get_unit_pid(unit_name: str) -> int:
    pid = get_unit_property(unit_name, "MainPID")
    pid = int(pid)
    if pid == 0:
        raise RuntimeError(f"Unit '{unit_name}' is not running")
    return pid


def get_systemctl_():
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        raise RuntimeError("Could not find systemctl executable")
    return systemctl


def get_unit_property(unit_name: str, property_name: str) -> str:
    result = subprocess.run(
        [get_systemctl_(), "show", "-P", property_name, unit_name],
        text=True,
        capture_output=True,
        check=True,
    )

    return result.stdout


def does_unit_exist(unit_name: str) -> bool:
    if not unit_name.endswith(".service"):
        unit_name = f"{unit_name}.service"

    result = subprocess.run(
        [get_systemctl_(), "list-unit-files", unit_name], capture_output=True
    )

    return result.returncode == 0
