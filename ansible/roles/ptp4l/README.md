# ptp4l Ansible Role

Installs and configures `ptp4l` from the LinuxPTP project for PTP synchronization.

For detailed documentation, see the [PTP Architecture Guide](../../../docs/ptp-architecture-guide.md).

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `ptp4l_instance_name` | no | `ptp4l` | Instance name (determines systemd unit and UDS name) |
| `ptp4l_interfaces` | **yes** | — | List of network interfaces (e.g., `["eno1", "enp2s0f0"]`) |
| `ptp4l_mode` | no | `client` | `client` (clientOnly=1) or `server` (serverOnly=1) |
| `ptp4l_config_file` | no | `/usr/share/doc/linuxptp/configs/default.cfg` | Absolute path to ptp4l config file |
| `ptp4l_uds_dir` | no | `/var/run` | Directory for Unix domain sockets |

## Example Usage

```yaml
- role: ptp4l
  vars:
    ptp4l_instance_name: eth0
    ptp4l_interfaces: ["eth0"]
    ptp4l_mode: server
```
