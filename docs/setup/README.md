# Setup

Install the repository-managed Docker Compose stack with the
[installation guide](installation.md), then choose an operating mode in
[configuration](configuration.md). These pages describe the current checkout;
use a release's matching documentation and templates when deploying that
release.

The stack contains the FastAPI backend, Mission Planner, Prometheus, and a
private GFS weather worker. Mission Planner provides the Overview and mission
workflow. Grafana is not part of this stack.

- [Quick start](quick-start.md)
- [Requirements](system-requirements.md)
- [Verify installation](installation-verification.md)
- [Troubleshooting](../troubleshooting/README.md)
- [Portainer/GHCR deployment](../deployment/portainer-ghcr.md)
- [Development workflow](../development/workflow.md)
