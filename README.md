# Synchronization Tool Suite

[![Build and test](https://github.com/tier4/sync_tooling/actions/workflows/build-and-test.yaml/badge.svg)](https://github.com/tier4/sync_tooling/actions/workflows/build-and-test.yaml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=tier4_sync_tooling&metric=alert_status&token=784a45ca7dc24a6bbde7badd4774612ccd458e82)](https://sonarcloud.io/summary/new_code?id=tier4_sync_tooling)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=tier4_sync_tooling&metric=coverage&token=784a45ca7dc24a6bbde7badd4774612ccd458e82)](https://sonarcloud.io/summary/new_code?id=tier4_sync_tooling)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Ftier4%2Fsync_tooling%2Frefs%2Fheads%2Fmain%2Fpyproject.toml%3Ftoken%3DGHSAT0AAAAAAC6B65T22THJU5J6SA2Y6CUMZ7BETVQ)


Tools for monitoring and diagnosing time synchronization in a distributed system.

The tools currently handle monitoring

- PTP4L logs (port states, clock state)
- PHC2SYS logs (servo state, offset)
- local and remote PTP instances by implementing a PTP Management Client

## Ansible (Recommended)

This tool can be installed on remote machines using Ansible.
First, create an inventory file akin to `ansible/x2gen2.yml` for your network architecture.

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
