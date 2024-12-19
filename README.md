# Synchronization Tool Suite

Tools for monitoring and diagnosing time synchronization in a distributed system.

The tools currently handle monitoring

- PTP4L logs (port states, clock state)
- PHC2SYS logs (servo state, offset)
- local and remote PTP instances by implementing a PTP Management Client

## Installation

### Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) as its package manager. You can install it via

```shell
pip install uv
```

### Building

```shell
git clone git@github.com:tier4/sync_tooling
cd sync_tooling
uv sync
uv run pytest
```

## Usage

```shell
# In the `sync_tooling` folder checked out above
uv run phc2sys-monitor
uv run ptp4l-monitor

# PMC monitor needs to run privileged so that it can communicate with local Unix domain sockets.
# See notes below.
sudo uv run pmc-monitor
```

> **Note:** To run `uv` privileged, it needs to be installed system-wide. If `sudo uv` does not work after a normal `pip install uv`, try `sudo pip install uv`.

