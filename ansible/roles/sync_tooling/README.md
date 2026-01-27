# sync_tooling Ansible Role

Downloads and installs SYNC.TOOLING Python packages from GitHub releases into a virtual environment.

For detailed documentation, see the [Installation Guide](../../../docs/installation.md).

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `sync_tooling_version` | no | `"0.2.5"` | Version to install (GitHub release tag without `v` prefix) |
| `sync_tooling_install_dir` | no | `/opt/sync_tooling` | Directory to install SYNC.TOOLING into |
| `sync_tooling_venv_path` | no | `{{ sync_tooling_install_dir }}/venv` | Directory to create virtual environment at |
| `sync_tooling_github_repo` | no | `tier4/sync_tooling` | GitHub repository to download from |
| `sync_tooling_python` | no | `python3` | Python interpreter to use |

About `sync_tooling_python`: This has to match the interpreter that ROS 2 was linked against.
This usually means your system `python3` installation.
