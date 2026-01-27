# diag_master Ansible Role

Configures the SYNC.TOOLING diagnostic master as a systemd service. The master aggregates
synchronization status updates from workers via ROS 2 topic `/sync_diag/graph_updates` and
provides diagnostics via ROS 2 topic `/diagnostics` (SYNC.DIAG) and an optional web UI
(SYNC.DOCTOR).

For detailed documentation, see the [Usage Guide](../../../docs/usage.md).

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `diag_master_ros_setup_script` | no | `/opt/ros/humble/setup.bash` | ROS 2 environment setup script |
| `diag_master_config_file` | no | `/etc/sync_tooling/diag_master.yml` | Path to the configuration file |
| `diag_master_config` | **yes** | `{}` | Configuration content (clock tree and thresholds) |
| `diag_master_enable_web_ui` | no | `false` | Enable web UI (SYNC.DOCTOR) on `http://0.0.0.0:5000` |
| `diag_master_topic` | no | `/sync_diag/graph_updates` | ROS 2 topic for receiving graph updates |
| `diag_master_update_expiry_s` | no | `2` | Seconds before a received graph update expires |
| `diag_master_ros_args` | no | `[]` | Additional ROS 2 arguments |
| `sync_tooling_venv_path` | no | `/opt/sync_tooling/venv` | Path to create virtual environment at |
