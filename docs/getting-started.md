SYNC.TOOLING can be installed on most distributed systems in a few simple steps. There are two
software components necessary:

- `diag-master` which provides the SYNC.DIAG ROS 2 diagnostics interface, and
- `diag-worker` which runs on every machine running LinuxPTP and provides updates to
   `diag-master`

## System Requirements

- Ubuntu 22.04
- ROS 2 Humble with Python3.10 (the default version on Ubuntu 22.04)
- All machines are in the same IP subnet and can communicate via ROS 2 pub/sub
- `pip` must be available

## Installation

First, clone the repository. This is common to all installation methods below.

```shell
git clone --recursive git@github.com:tier4/sync_tooling.git
cd sync_tooling

# Downloads build tool and builds the project
./setup
```

### with Ansible <small>recommended</small>

[Ansible](https://docs.ansible.com/) is the quickest and easiest way to install SYNC.TOOLING.
The repository provides a playbook to one-click install the software onto all systems in a
distributed architecture.

There are two more requirements in addition to the ones above:

- the machine that runs the playbook must be connected to the internet during installation
- all other machines must be accessible from that machine via SSH

Installation then is as simple as

```shell
./distribute path/to/inventory.yml
```

This script does multiple things:

- ensure the host has a usable SSH ID (currently only `id_rsa.pub` is recognized, see [#1][1])
- copy that SSH ID to all remote machines in the inventory
    - requires entering the password for each machine once
    - unreachable machines, and those with the ID already present are skipped
- open a temporary proxy for the remote machines to be able to use `apt`, `pip`, etc.
- runs the playbook that installs SYNC.TOOLING

The inventory passed above has to be of the following shape:

```yaml
all:
  vars:
    remote_user: example_user
  hosts: # (1)!
    full_example: # (2)!
      ansible_host: 192.168.1.1 # (3)!
      sync_master: # (4)!
        reference: /path/to/reference_graph.yml # (5)!
      sync_worker: # (6)!
        ptp4l_units: # (7)!
          - ptp4l@eno1 # (8)!
          - ptp4l@eno2
        phc2sys_units: # (9)!
          - phc2sys_sys_to_eno1 # (10)!
          - phc2sys_sys_to_eno2
    only_one_ptp4l_unit:
      ansible_host: 192.168.1.2
      remote_user: another_user # (11)!
      sync_worker:
        ptp4l_units: 
          - ptp4l
        phc2sys_units: [] # (12)!
```

1. The list of hosts to deploy to.
2. While arbitrary names are allowed, it is recommended to use the hostname of the machine as
   the name.
3. The IP address of the machine.
4. If present, a diag-master instance will be installed on this machine.
5. The path to the reference graph file. Absolute or relative to the `ansible` directory.
6. If present, a sync-worker instance will be installed on this machine.
7. The list of ptp4l units to monitor. Can be left empty (`[]`).
8. The name of the systemd unit. Names in the format `ptp4l@<interface>` are recommended.
9. The list of phc2sys units to monitor. Can be left empty (`[]`).
10. The name of the systemd unit. Names in the format `phc2sys_<source>_to_<target>` are recommended.
11. Users can also be specified per-host.
12. Although there are no units, this key must be present.

Note that there can be up to one diag-master and up to one diag-worker per machine.
It is thus also possible to have both on the same machine.

!!! note
    While it is possible to have multiple diag-masters across multiple machines, they will both
    be publishing to the same ROS 2 `/diagnostics` topic. This can be dealt with by remapping
    using the `--ros-args` argument of `diag-master` but there is currently no way to set this
    argument from ansible.

Once `distribute` has finished, a systemd service will have been created and started for each
diag-master and diag-worker instance.

[1]: https://github.com/tier4/sync_tooling/issues/1

### building manually

This project is built using [uv](https://docs.astral.sh/uv/), a modern Python package manager.
It will already be installed on the machine if the `./setup` script was used.

The build process is done in two steps:

```shell
uv sync --all-packages
uv build --all-packages
```

This will generate a `dist` directory with the built packages, and the `sync_tooling-<...>.whl`
can be installed using `pip`.

```shell
uv export > requirements.txt
pip install -r requirements.txt
pip install dist/sync_tooling-*.whl
```

Instead of installing the program globally, it can be easily run via
[`uv run`](https://docs.astral.sh/uv/reference/cli/#uv-run):

```shell
uv run diag-master <...>
uv run diag-worker <...>
```

`uv` takes care of creating a virtual environment and installing the dependencies.

## Usage

In case the software was installed via Ansible, the command lines of these programs have already
been configured in the generated systemd service files.

### `diag-worker` command

See available command line arguments with

```shell
uv run diag-worker --help
```

By default, `diag-worker` will publish updates to the ROS 2 topic`/sync_diag/graph_updates`.
The monitored `ptp4l` and `phc2sys` units have to be specified with the `--ptp4l-units` and
`--phc2sys-units` arguments, respectively.

!!! warning
    There can only be one `diag-worker` per machine.

!!! warning
    If there are multiple `ptp4l` units on the same machine, their `uds_address`es must be
    unique. We recommend, that for unit `ptp4l@xyz` the `uds_address` is set to
    `/var/run/ptp4l@xyz`. Set either via `ptp4l`'s `uds_address` config option or via its
    `--uds_address` command line argument.

### `diag-master` command

See available command line arguments with

```shell
uv run diag-master --help
```

By default, `diag-master` will listen to updates from workers on the ROS 2 topic
`/sync_diag/graph_updates` and publish diagnostics to `/diagnostics`.
The web interface is launched on `0.0.0.0:5000`.

!!! warning
    There can only be one `diag-master` per machine. In general, only one is needed per
    distributed system (i.e. per vehicle).

By specifying a `--reference` graph, the master will use that graph for advanced diagnostics.

A reference graph is a tree of clocks, with each parent having a direct PTP or PHC2SYS link to
each of its children. The reference graph is needed because not every part of the distributed
system is observable, and SYNC.TOOLING has to make sure that all clocks are synchronized in the
way the user intended.

The reference graph is specified in YAML format. An example is given below:

```yaml
clock_tree: # (1)!
  main_ecu.sys: # (2)!
    main_ecu.ptp0: # (3)!
      sensing_ecu.sys: # (4)!
        lidar/left: # (5)!
        lidar/right: # (6)!
    main_ecu.ptp1:
      radar/front:
      radar/rear:
```

1. The root of the tree is the grandmaster clock of the system.
2. The reference graph has to be located under the `clock_tree` key.
3. The pattern `<hostname>.ptp<n>` is used to identify a hardware clock device of an ECU.
4. The pattern `<hostname>.sys` is used to identify the system clock of an ECU.
5. The pattern `<tf2/frame/id>` is used to identify a sensor.
6. Even entries with no children need a `:` at the end.

<!-- markdownlint-disable MD046 -->
!!! warning
    Special care needs to be taken to define hardware and software time stamping correctly:
    If PTP4L is using software time stamping `-S`, the corresponding clock is the ECU's system
    clock.

    If hardware time stamping is used on a given `-i <interface>`, find the clock e.g.
    using `ethtool -T <interface>`. E.g., if `ethtool -T eno1` prints 
    `[...] PTP Hardware Clock: 0 [...]`, the clock is `ptp0`.
<!-- markdownlint-enable MD046 -->

### SYNC.DIAG

The `diag-master` publishes diagnostics to the ROS 2 topic `/diagnostics`.
We label this functionality as SYNC.DIAG.

This functionality is only fully enabled if a `--reference` graph has been provided to the
`diag-master`.

### SYNC.DOCTOR

The `diag-master` provides a web interface named SYNC.DOCTOR.
This interface allows for live or offline viewing of the synchronization state of the system.

### Offline Analysis

To record synchronization state for later analysis, run:

```shell
ros2 bag record /sync_diag/graph_updates
```

The expected data rate is about `1 kB/s` per `ptp4l`, `phc2sys` or sensor instance.
For an architecture like X2 gen2, this results in a data rate of about `14 kB/s`.

The bag can be replayed at a later time on any machine with only a `diag-master` running:

```shell
ros2 bag play <path_to_bag>
```

Both SYNC.DIAG and SYNC.DOCTOR will respond live to the replay.
