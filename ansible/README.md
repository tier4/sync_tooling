# SYNC.TOOLING Ansible Roles

Ansible roles for installing and configuring PTP synchronization and SYNC.TOOLING diagnostics.
These cover most basic use cases but might need customization when dealing with

- advanced PTP4L / PHC2SYS command line arguments
- systemd service launch order

For detailed documentation, see the [Installation Guide](../docs/installation.md) and
[Usage Guide](../docs/usage.md).

## Available Roles

| Role | Description |
|------|-------------|
| [ptp4l](roles/ptp4l/README.md) | Install and configure ptp4l (PTP daemon) |
| [phc2sys](roles/phc2sys/README.md) | Configure phc2sys for synchronizing local clocks |
| [sync_tooling](roles/sync_tooling/README.md) | Download and install SYNC.TOOLING from GitHub releases |
| [diag_worker](roles/diag_worker/README.md) | Configure the diagnostic worker systemd service |
| [diag_master](roles/diag_master/README.md) | Configure the diagnostic master systemd service |

## Example

See [examples/](examples/) for a complete two-ECU playbook demonstrating:

- PTP master/client configuration
- phc2sys UTC/TAI conversion
- Diagnostic master and worker setup
