# Copyright 2025 TIER IV, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility functions for LinuxPTP monitoring."""

import re
import socket


def get_hostname() -> str:
    """Get the system hostname.

    Raises:
        RuntimeError: If hostname cannot be determined.

    Returns:
        The system hostname.

    """
    hostname = socket.gethostname()
    if not hostname:
        raise RuntimeError("Could not determine hostname")
    return hostname


def hostname_to_node_name(hostname: str) -> str:
    """Convert a hostname to a valid ROS 2 node name.

    Replaces unsupported characters. A ROS 2 node name must match `^[A-z][A-z0-9_]*$`.

    See Also:
        https://wiki.ros.org/Names
    """
    # Replace each chain of unsupported characters with an underscore
    node_name = re.sub(r"\W+", "_", hostname)

    # If the first character is not a letter, prepend one
    if not node_name or not node_name[0].isalpha():
        node_name = "host_" + node_name

    assert re.match(r"^[A-z][A-z0-9_]*$", node_name)
    return node_name
