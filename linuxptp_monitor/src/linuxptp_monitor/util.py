import re
import socket


def get_hostname() -> str:
    hostname = socket.gethostname()
    if not hostname:
        raise RuntimeError("Could not determine hostname")
    return hostname


def hostname_to_node_name(hostname: str) -> str:
    """
    Convert a hostname to a valid ROS 2 node name by replacing unsupported characters.
    A ROS 2 node name must be of the form `^[A-z][A-z0-9_]*$`, see: https://wiki.ros.org/Names
    """

    # Replace each chain of unsupported characters with an underscore
    node_name = re.sub(r"\W+", "_", hostname)

    # If the first character is not a letter, prepend one
    if not node_name or not node_name[0].isalpha():
        node_name = "host_" + node_name

    assert re.match(r"^[A-z][A-z0-9_]*$", node_name)
    return node_name
