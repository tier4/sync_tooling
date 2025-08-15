This manual is for teams that want to integrate SYNC.DIAG into their vehicle architecture.
The guide covers not only SYNC.DIAG configuration but also PTP architecture configuration.
It is assumed that the vehicle is using [Pilot Auto][pilot-auto], is set up using Ansible,
and has access to [Autoware ECU System Setup][autoware-ecu-system-setup] Ansible roles.

[pilot-auto]: https://github.com/tier4/pilot-auto
[autoware-ecu-system-setup]: https://github.com/tier4/autoware_ecu_system_setup

# Pre-Requisites

The ECU, sensor and network architecture has been decided and set up. This includes things like
Netplan configuration and IP address assignments.

The network architecture has to be compatible with the specific ECUs' and sensors' supported
PTP profiles.

ECUs typically have multiple clocks: one system clock and multiple hardware clocks, usually
one per network interface. These have to be synchronized to each other (locally on the ECU), so
be sure to understand which clocks are available.

# PTP Architecture

While an exhaustive guidebook on PTP is hard to provide, due to the complexity of the topic,
this guide provides common pointers and pitfalls to avoid when setting up PTP.

## PTP Software

There are two common software stacks for PTP on Linux: `linuxptp` and `ptpd`. `linuxptp`
provides a more feature-rich implementation with its `ptp4l` and `phc2sys` programs and is the
recommended choice for most use cases.

!!! warning
    SYNC.TOOLING only supports `linuxptp`. `ptpd` is unsupported.

!!! tip
    Use `linuxptp` unless there is a strong reason not to.

`ptp4l` participates in PTP synchronization over the network on one or more interfaces.
It is configured with one local clock and will synchronize it to the best available PTP clock
on the network (slave mode) or let other devices synchronize to it (master mode).

`phc2sys` is used to synchronize multiple clocks on the same ECU, e.g. the system clock and
a network interface's hardware clock.

Install and configure PTP4L and PHC2SYS via the [autoware_ecu_system_setup.ptp4l][role-ptp4l]
role, or via custom roles.

[role-ptp4l]: https://github.com/tier4/autoware_ecu_system_setup/tree/590fabea4f21811a0a69e26793e4fff4f9b60bd1/roles/ptp4l

## PTP Profiles

There are three main PTP profiles:

| Profile        | Description                                        |
| -------------- | -------------------------------------------------- |
| PTPv2 (1588v2) | The least precise, but most forgiving profile.     |
| gPTP (802.1AS) | More precise, but highly restrictive requirements. |
| Automotive     | A gPTP profile tuned for automotive use cases.     |

Which one to use depends on hardware support and network architecture.

!!! bug
    Do not mix PTP profiles in the same network segment, as this can lead to synchronization
    faults.

!!! bug
    Never launch multiple `ptp4l` or `ptpd` instances on the same network interface, as this
    can lead to synchronization faults.

### PTPv2

This is the most easily deployed profile. It can be used on bus-like network links with many
participants, and can use UDP/IP transport.

PTPv2

* can run over UDPv4 (`-4`), UDPv6 (`-6`), or raw Ethernet/L2 (`-2`).
* supports time stamping in software (`-S`) or hardware (`-H`).
* can operate in either end-to-end (`-E`) or peer-to-peer (`-P`) mode.

!!! bug
    Do not mix software and hardware time stamping between a master and slave, as implicit
    UTC-TAI conversions will lead to time offsets of roughly 37 seconds.

!!! bug
    Do not mix end-to-end and peer-to-peer mode in the same network segment, as this can lead
    to synchronization faults.

!!! tip
    Use hardware time stamping (`-H`) where possible. Use UDPv4 (`-4`) for easy network setup.
    Use peer-to-peer mode (`-P`) for best performance. If there are compatibility issues,
    fall back to end-to-end mode (`-E`).

### gPTP, Automotive

These profiles are highly restrictive. Network equipment like switches has to support the
profile, and all network links where the profile is used have to be 1-to-1.

Use these if they are required by the hardware, such as automotive sensors.

!!! bug
    Do not run gPTP or Automotive PTP on network links with more than two participants,
    as this will lead to synchronization faults.

As a case study, X2 gen2 is using a switch that does not support gPTP, so it was necessary
to configure the switch to forward PTP traffic in a way that simulates many 1-to-1 links.
See [X2 gen2 PTP troubleshooting](https://tier4.atlassian.net/wiki/x/jIAvwg) for details.

# SYNC.DIAG

Once a PTP architecture is set up, SYNC.DIAG can be configured to monitor synchronization
status and publish it to ROS 2.

Install and configure SYNC.DIAG via the [autoware_ecu_system_setup.sync_tooling][role-sync-tooling]
role on every ECU that participates in PTP synchronization.

[role-sync-tooling]: https://github.com/tier4/autoware_ecu_system_setup/tree/590fabea4f21811a0a69e26793e4fff4f9b60bd1/roles/sync_tooling
