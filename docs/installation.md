SYNC.TOOLING can be installed on most distributed systems in a few simple steps. There are two
software components necessary:

- `diag-master` which provides the SYNC.DIAG ROS 2 diagnostics interface, and
- `diag-worker` which runs on every machine running LinuxPTP and provides updates to
   `diag-master`

!!! tip
    If you are an integrator, or using Pilot.Auto, please refer to the
    [Integrators Guide](integrators-guide.md) for automated setup instructions.

--8<-- "README.md:installation"

## Usage
<!-- markdownlint-disable MD051 -->
If the software was installed globally via `pip` (see [Production Build](#production-build)),
the below tools should be available in your `PATH`. Use them directly:

```shell
diag-master
diag-worker
```

If the software was installed via `uv` (see [Development Build](#development-build)), the tools
are available in the `uv` virtual environment. Use `uv run` to run the tools:
<!-- markdownlint-enable MD051 -->

```shell
cd <path/to/sync_tooling>
uv run diag-master
uv run diag-worker
```

### `diag-worker` command

See available command line arguments with

```shell
diag-worker --help
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
diag-master --help
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
