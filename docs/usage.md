In case the software was installed via Ansible, the command lines of these programs have already
been configured in the generated systemd service files.

## `diag-worker` command

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

## `diag-master` command

See available command line arguments with

```shell
uv run diag-master --help
```

By default, `diag-master` will listen to updates from workers on the ROS 2 topic
`/sync_diag/graph_updates` and publish diagnostics to `/diagnostics`.
The web interface is launched on `0.0.0.0:5000` if launched with the `--web-ui` option.

!!! warning
    There can only be one `diag-master` per machine. In general, only one is needed per
    distributed system (i.e. per vehicle).

### Configuration

A configuration file must be specified with the `--config` option.
This file contains the reference graph of the system, along with diagnostic thresholds and other
options.

A reference graph is a tree of clocks, with each parent having a direct PTP or PHC2SYS link to
each of its children. Using the reference graph, SYNC.TOOLING can confirm if all clocks are
synchronized in the way the user intended.

The config is specified in YAML format. An example is given below:

```yaml
clock_tree: # (1)!
  main_ecu.sys: # (2)!
    main_ecu.ptp0: # (3)!
      sensing_ecu.ptp0:
        sensing_ecu.sys: # (4)!
        sensor@lidar/left: # (5)!
        sensor@lidar/right: # (6)!
    main_ecu.ptp1:
      sensor@radar/front:
      sensor@radar/rear:
diagnostics:
  diff_thresholds: # (7)!
    ptp_master: # (8)!
      warn: 100
      error: 1000
      unit: us
    phc2sys: # (9)!
      warn: 100
      error: 1000
      unit: us
    measurement: # (10)!
      warn: 1
      error: 20
      unit: ms
```

1. The root of the clock tree (= the reference graph) is the grandmaster clock of the system.
2. The reference graph has to be located under the `clock_tree` key.
3. The pattern `<hostname>.ptp<n>` is used to identify a hardware clock device of an ECU.
4. The pattern `<hostname>.sys` is used to identify the system clock of an ECU.
5. The pattern `<tf2/frame/id>` is used to identify a sensor.
6. Even entries with no children need a `:` at the end.
7. These are customizable thresholds to diagnose reported time differences.
8. For a PTP link, the PTP master reports the time difference to a child clock, as calculated
   by PTP. This is usually very accurate and low-variance.
9. For a PHC2SYS link, PHC2SYS reports the time difference between source and child clock.
   This is usually very accurate and low-variance.
10. For a measurement link, the time difference is measured by SYNC.TOOLING. This is usually
    less accurate and more variable than the other two.

!!! warning
    Special care needs to be taken to define hardware and software time stamping correctly:
    If PTP4L is using software time stamping `-S`, the corresponding clock is the ECU's system
    clock.

    If hardware time stamping is used on a given `-i <interface>`, find the clock e.g.
    using `ethtool -T <interface>`. E.g., if `ethtool -T eno1` prints 
    `[...] PTP Hardware Clock: 0 [...]`, the clock is `ptp0`.

!!! tip
    Refer to the
    [example configuration](https://github.com/tier4/sync_tooling/blob/main/diag_master/config/example.yml)
    for the most up-to-date information.

## SYNC.DIAG

The `diag-master` publishes diagnostics to the ROS 2 topic `/diagnostics`.
We label this functionality as SYNC.DIAG.

This functionality is only fully enabled if a `--reference` graph has been provided to the
`diag-master`.

## SYNC.DOCTOR

The `diag-master` provides a web interface named SYNC.DOCTOR.
This interface allows for live or offline viewing of the synchronization state of the system.

## Offline Analysis

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
