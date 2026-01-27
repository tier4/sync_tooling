# diag_worker Ansible Role

Configures the SYNC.TOOLING diagnostic worker as a systemd service. The worker monitors local
`ptp4l` and `phc2sys` instances and publishes synchronization status updates to ROS 2.

For detailed documentation, see the [Usage Guide](../../../docs/usage.md).

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `diag_worker_ros_setup_script` | no | `/opt/ros/humble/setup.bash` | ROS 2 environment setup script |
| `diag_worker_ptp4l_units` | no | `[]` | List of ptp4l systemd unit names to monitor |
| `diag_worker_phc2sys_units` | no | `[]` | List of phc2sys systemd unit names to monitor |
| `diag_worker_topic` | no | `/sync_diag/graph_updates` | ROS 2 topic for publishing graph updates |
| `diag_worker_ros_args` | no | `[]` | Additional ROS 2 arguments |
| `sync_tooling_venv_path` | no | `/opt/sync_tooling/venv` | SYNC.TOOLING virtual environment path |
