This manual is for teams that want to integrate SYNC.DIAG into their vehicle architecture.

It is assumed that the vehicle is set up using Ansible. This repository provides Ansible roles
for PTP and SYNC.TOOLING configuration in the [`ansible/`](https://github.com/tier4/sync_tooling/tree/main/ansible)
directory.

## Pre-Requisites

### Setup ECU IP Configuration and PTP

The ECU, sensor and network architecture has been decided and set up. This includes things like
Netplan configuration and IP address assignments.

The network architecture has to be compatible with the specific ECUs' and sensors' supported
PTP profiles.

The [PTP Architecture Guide](ptp-architecture-guide.md) has been followed to set up the
PTP architecture, including all PTP4L and PHC2SYS configuration.

### Setup Diagnostics in Sensor Driver

Setup `nebula>=v0.2.8` and sensor configuration to output synchronization meta data on `/sync_diag/graph_updates`.

Please check the configuration example in [this PR](https://github.com/tier4/aip_launcher/pull/529)

## SYNC.DIAG

Once a PTP architecture is set up, SYNC.DIAG can be configured to monitor synchronization
status and publish it to ROS 2.

### Setup

Install and configure SYNC.DIAG using the Ansible roles provided in this repository:

- [`diag_worker`][diag-worker-role] - Run on every ECU with PTP
- [`diag_master`][diag-master-role] - Run once per vehicle

[diag-worker-role]: https://github.com/tier4/sync_tooling/tree/main/ansible/roles/diag_worker
[diag-master-role]: https://github.com/tier4/sync_tooling/tree/main/ansible/roles/diag_master

The SYNC.DIAG Master is only required once, and should be run on an ECU that publishes or
processes ROS 2 `/diagnostics`. Usually, the main Autoware ECU is a good choice.

SYNC.DIAG Workers are required on every ECU that participates in PTP synchronization, including
the one running the SYNC.DIAG Master. Each worker has to be configured with a list of
`ptp4l` and `phc2sys` instances to monitor.

!!! info "Named Unix Domain Sockets"
    When using the `ptp4l` Ansible role from this repository, each instance automatically gets
    a unique Unix domain socket at `/var/run/ptp4l@<name>`. This is required for SYNC.TOOLING
    to communicate with `ptp4l` instances.

All ECUs running a SYNC.DIAG Worker and/or Master must be able to communicate over ROS 2, as
the `/sync_diag/graph_updates` topic is used to send status updates to the master.

More information on requirements can be found in the [Manual Installation Guide](installation.md).

More information on the required configuration file can be found in the [Usage Guide](usage.md).

### Example Playbook

```yaml
--8<-- "ansible/examples/playbook.yml"
```

### Running SYNC.DIAG

SYNC.DIAG is started automatically as a systemd service on every ECU that has been configured.
To make sure it is working correctly, check the output in ROS 2 `/diagnostics`. Also check
that none of the services crash or fail to start.

### Running SYNC.DOCTOR

To access the web interface SYNC.DOCTOR, the SYNC.DIAG Master has to be launched with the
`--web-ui` option. This will start a web server on port `5000` of the ECU running the master.
