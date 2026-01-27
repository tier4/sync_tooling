# phc2sys Ansible Role

Installs and configures `phc2sys` from the LinuxPTP project for clock synchronization
(e.g., PHC to system clock).

For detailed documentation, see the [PTP Architecture Guide](../../../docs/ptp-architecture-guide.md).

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `phc2sys_instance_name` | no | `phc2sys` | Instance name (determines systemd unit name) |
| `phc2sys_source` | **yes** | — | Source clock (e.g., `CLOCK_REALTIME`, `/dev/ptp0`) |
| `phc2sys_destinations` | **yes** | — | List of destination clocks (e.g., `["/dev/ptp0", "CLOCK_REALTIME"]`) |
| `phc2sys_utc_offset` | no | `0` | Seconds to add to source time (e.g., `37` for UTC to TAI) |
| `phc2sys_wait_for_ptp` | no | `false` | Wait for ptp4l to stabilize before starting sync |
| `phc2sys_ptp4l_uds` | no | `""` | ptp4l Unix domain socket to monitor (for `-u` flag) |

## Example Usage

```yaml
- role: phc2sys
  vars:
    phc2sys_instance_name: sys_to_eth0
    phc2sys_source: CLOCK_REALTIME
    phc2sys_destinations: ["/dev/ptp0"]
    phc2sys_utc_offset: 37
```
