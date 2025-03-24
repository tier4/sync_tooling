# Synchronization Tool Suite

[![CI](https://github.com/tier4/sync_tooling/actions/workflows/build-and-test.yaml/badge.svg)](https://github.com/tier4/sync_tooling/actions/workflows/build-and-test.yaml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=tier4_sync_tooling&metric=alert_status&token=784a45ca7dc24a6bbde7badd4774612ccd458e82)](https://sonarcloud.io/summary/new_code?id=tier4_sync_tooling)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=tier4_sync_tooling&metric=coverage&token=784a45ca7dc24a6bbde7badd4774612ccd458e82)](https://sonarcloud.io/summary/new_code?id=tier4_sync_tooling)
![Python Version](https://img.shields.io/badge/python->=3.10-blue)


Tools for monitoring and diagnosing time synchronization in a distributed system.

The tools currently handle monitoring

- PTP4L logs (port states, clock state)
- PHC2SYS logs (servo state, offset)
- local and remote PTP instances by implementing a PTP Management Client

## Ansible (Recommended)

This tool can be installed on remote machines using Ansible.
First, create an inventory file akin to `ansible/x2gen2.yml` for your network architecture.

To set up dependencies on the host machine, run
```shell
./setup
```

Then, to satisfy dependencies and install worker executables on the worker machines, run
```shell
./distribute path/to/inventory.yml
```

> **Note:** If you have not set up SSH key-based authentication from the host to the inventory
> machines, this script will generate and install SSH keys to all the inventory machines.

> **:warning: Caution:** **Never use password-less SSH keys in any production system!** 

Done :tada:!

## Manual Installation

This has to be done for every machine that sync tooling should run on.

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
uv run diag-master 0.0.0.0

# The diag-worker needs to run privileged so that it can communicate with local Unix domain sockets and read the journal of services running with elevated privileges
# See notes below.
sudo uv run diag-worker --ptp4l-units ptp4l@eno1 ptp4l@enp3s0 -- 127.0.0.1
```

> **Note:** To run `uv` privileged, it needs to be installed system-wide. If `sudo uv` does not work after a normal `pip install uv`, try `sudo pip install uv`.
