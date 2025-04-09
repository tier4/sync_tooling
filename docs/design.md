SYNC.TOOLING is designed to ensure that the given distributed system, including ECUs,
sensors and other network equipment, is synchronized correctly.

While software like [LinuxPTP](https://sourceforge.net/projects/linuxptp/) and its command line
programs `ptp4l` and `phc2sys` can ensure reliable synchronization, they do not make their
diagnostics available to other programs.
Further, equipment like sensors might not support common diagnostics protocols at all,
necessitating custom means of ensuring correct synchronization.

## Requirements

SYNC.TOOLING is required to

- provide online real-time[^3] diagnostics
  - to ROS 2 (SYNC.DIAG) and
  - via web interface (SYNC.DOCTOR)
  - for pre-existing setups (e.g. vehicles set up before SYNC.TOOLING became available)
- be shippable as systemd services
- be one-click installable for troubleshooting purposes
- neither raise false positives (e.g. triggering MRM on a transient fault)
- nor report actual faults too late or not at all

## General Assumptions

In designing this software suite, the following assumptions have been made:

- the time synchronization mechanism is PTPv2[^1]
- all ECUs that participate in PTP time synchronization
  - are running `ptp4l` to synchronize with other network devices
  - are running `phc2sys` to synchronize their internal clocks (if there are multiple)
  - are running `ptp4l` and `phc2sys` instances as systemd units
  - are not performing any other time synchronization, e.g. using `ptpd` or non-systemd units
- all sensors that participate in PTP provide a way to compare their clock with another one
  in the system
  - for example, sending timestamps in their packets, that can then be compared with the
    receiving ECU's clock
- not all devices that participate in time synchronization are fully observable
  - for example, some devices might not have any diagnostics interfaces
  - some devices might only report status information, but no info on their parent or master
    PTP instances
- in case of synchronization loss, clocks take multiple seconds[^2] to drift far enough apart
  to be problematic
- `ptp4l` and `phc2sys`

[^1]: Specifically
  [IEEE 1588v2 (PTPv2)](https://standards.ieee.org/ieee/1588/4355/),
  [IEEE 802.1AS (gPTP)](https://standards.ieee.org/ieee/802.1AS/7121/) or
  [AutoSAR EthTSyn (gPTP Automotive Profile)][5]

[^2]: This should be in the order of tens of seconds, but we are, somewhat arbitrarily,
  defining this as `5s` here.

[5]: https://www.autosar.org/fileadmin/standards/R21-11/CP/AUTOSAR_SWS_TimeSyncOverEthernet.pdf

## Diagnostics Requirements

Diagnostics must be made available in real-time[^3] to ROS 2 `/diagnostics` in a manner
compatible with the [Autoware Diagnostics API][6].

The diagnostics shall be updated as often as necessary but in any case faster than the `5s`[^2]
deadline imposed above. For the time being, `1s` seems to be a good compromise[^4].

As for the actual diagnostics output, it is required that

- for every clock, the status of the synchronization to the grandmaster[^5] is diagnosed
- for missing clocks to be detected and reported
- for cycles or disconnected subgraphs to be detected and reported

[^3]: Both in the sense of the strict definition (the computations must complete by a certain
  periodic deadline), and in the sense that diagnostics are live (at most a few seconds out of
  date). See [real-time computing](https://en.wikipedia.org/wiki/Real-time_computing).

[^4]: This allows for momentary faults in communication without raising a diagnostic error.
  Further, some tools like `pmc` are too slow to operate reliably at a sub-second frequency.

[^5]: The term "grandmaster" is defined in the PTP standard, but the usage here refers to the
  clock that all other clocks synchronize to, even through means other than PTP (such as
  PHC2SYS).

[6]: https://autowarefoundation.github.io/autoware-documentation/main/design/autoware-interfaces/ad-api/features/diagnostics/

## System Architecture

![Diagnostics [Architecture]](img/sync_tooling.drawio)

## Tech Stack

The following technologies are used:

| Technology          | Usage                         | Rationale                                                                    |
| ------------------- | ----------------------------- | ---------------------------------------------------------------------------- |
| Python 3.10         | All program logic             | Type system, ease of interfacing with, development speed                     |
| [Protobuf][1]       | Internal interfaces           | Support for sum types (oneof), self-referential data structures (e.g. trees) |
| ROS 2               | Transport layer               | Familiarity, no additional network setup necessary                           |
| ROS 2               | Diagnostics (SYNC.DIAG)       | Interoperability with Autoware                                               |
| [Flask][2]          | Web server (SYNC.DOCTOR)      | Fast and simple, other frameworks such as FastAPI would be fine too          |
| [Apache ECharts][3] | Graph rendering (SYNC.DOCTOR) | Design, smoothness, ease of integration                                      |
| [NetworkX][4]       | Graph analysis                | De-facto standard graph analysis library for Python                          |

[1]: https://protobuf.dev/
[2]: https://flask.palletsprojects.com/en/stable/
[3]: https://echarts.apache.org/en/index.html
[4]: https://networkx.org/documentation/stable/index.html
