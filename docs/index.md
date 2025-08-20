# SYNC.TOOLING

Takes the **pain** out of **p**recision time synchroniz**a**t**i**o**n**.

{{ visualize_sync_doctor_echart("diag_master.examples.example_graph") | safe }}

* :simple-ansible: one-click deployable with Ansible
* :material-graph: monitors the whole vehicle architecture
* :octicons-sync-16: integrates with your existing LinuxPTP setup
* :simple-ros: plug-and-play compatible with ROS 2 `/diagnostics`
* :octicons-browser-16: confirm system state live in the browser

Set up SYNC.TOOLING for a Pilot.Auto based system: [Integrators' Guide](integrators-guide.md)
Set up SYNC.TOOLING manually: [Manual Installation Guide](installation.md)
Configure SYNC.TOOLING: [Usage Guide](usage.md)

Learn more about setting up a PTP architecture: [PTP Architecture Guide](ptp-architecture-guide.md)

## :material-tools: SYNC.SETUP

Try before you buy: validate your architecture from day one.

Define your architecture as a simple YAML file, and let SYNC.SETUP generate PTP4L, PHC2SYS
and sensor configurations. Any issues or incompatibilities are flagged right away.

* [ ] This feature is not yet available.

## :material-stethoscope: SYNC.DOCTOR

Troubleshoot at the scene or from your desk.

Visualize the current and past states of the system and gain insights on where synchronization fails.

* [x] This feature is fully supported.

## :material-heart-pulse: SYNC.DIAG

Know and react when something is off: ROS 2 diagnostics from clock to system level.

SYNC.DIAG monitors every clock and synchronization link in your system for errors and immediately
publishes diagnostics for affected devices.

* [x] This feature is fully supported.
