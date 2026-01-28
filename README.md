# Synchronization Tool Suite

[![CI](https://github.com/tier4/sync_tooling/actions/workflows/build.yaml/badge.svg)](https://github.com/tier4/sync_tooling/actions/workflows/build.yaml)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=tier4_sync_tooling&metric=coverage&token=784a45ca7dc24a6bbde7badd4774612ccd458e82)](https://sonarcloud.io/summary/new_code?id=tier4_sync_tooling)
![Python Version](https://img.shields.io/badge/python->=3.10-blue)

Tools for monitoring and diagnosing time synchronization in a distributed system.

The tools currently handle monitoring

- PTP4L logs (port states, clock state)
- PHC2SYS logs (servo state, offset)
- local and remote PTP instances by implementing a PTP Management Client

Documentation is available at [**sync-tooling.pages.dev**](https://sync-tooling.pages.dev/) :book:
(log in with your `@tier4.jp` email address).

<!-- --8<-- [start:installation] -->
## System Requirements

- Ubuntu >= 22.04
- ROS 2 >= Humble
- Python >= 3.10

For diag-worker, the following additional requirements apply:

- Ethtool (`sudo apt install ethtool`)
- PTP4L and PHC2SYS (`sudo apt install linuxptp`)

## Installation

SYNC.TOOLING has to be installed on every machine that will run a diag-master or a diag-worker.

### Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) as its package manager.
You can install it via

```shell
pip install uv
```

### Development Build

This method builds the project locally for development purposes.

```shell
git clone --recursive https://github.com/tier4/sync_tooling.git
cd sync_tooling

uv sync --all-packages

# Replace `humble` with your ROS 2 distro name, e.g. jazzy.
source /opt/ros/humble/setup.bash
uv run pytest
```

### Production Build

This method builds Python packages (wheel files) that can be installed using `uv` or `pip`.

```shell
git clone --recursive https://github.com/tier4/sync_tooling.git
cd sync_tooling

uv build --all-packages
```

This will generate a `dist` directory with the built packages, and the `dist/*.whl` files can be
installed using `pip`:

```shell
pip install dist/*.whl
```
<!-- --8<-- [end:installation] -->

## Usage

```shell
# In the `sync_tooling` folder checked out above
uv run diag-master --reference diag_master/config/sample.yml

# The diag-worker needs to run privileged so that it can communicate with local Unix domain 
# sockets and read the journal of services running with elevated privileges
# See notes below.
sudo uv run diag-worker --ptp4l-units ptp4l@eno1 ptp4l@enp2s0
```

> **Note:** To run `uv` privileged, it needs to be installed system-wide. If `sudo uv` does not
> work after a normal `pip install uv`, try `sudo pip install uv`.
