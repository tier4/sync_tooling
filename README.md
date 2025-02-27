# Synchronization Tool Suite

Tools for monitoring and diagnosing time synchronization in a distributed system.

The tools currently handle monitoring

- PTP4L logs (port states, clock state)
- PHC2SYS logs (servo state, offset)
- local and remote PTP instances by implementing a PTP Management Client

## Ansible (Recommended)

This tool can be installed on remote machines using Ansible.
First, create an inventory file akin to `ansible/***REMOVED***.yml` for your network architecture.

To set up dependencies on the host machine and to enable SSH-key-based login on the remote workers, run
```shell
./setup path/to/inventory.yml
```

Then, to satisfy dependencies and install worker executables on the worker machines, run
```shell
./distribute path/to/inventory.yml
````

Done :tada:!

## Manual Installation

### Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) as its package manager. You can install it via

```shell
pip install uv
```

### Building

```shell
git clone git@github.com:tier4/sync_tooling
cd sync_tooling
uv sync --all-packages
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
