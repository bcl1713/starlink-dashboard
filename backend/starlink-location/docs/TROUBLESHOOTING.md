# Backend Troubleshooting

Use the
[current diagnostics](../../../docs/troubleshooting/quick-diagnostics.md) for
service readiness, configuration, network access, and telemetry issues. From
repository root, inspect the intended Compose project:

```bash
docker compose ps
docker compose logs --tail=100 starlink-location
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/api/status
```

For a port conflict, identify the listener and its owner before changing ports
or stopping a process. Stop only resources you own, gracefully first. Do not use
blanket process-kill or Docker prune commands.

For managed cloud environments, preserve the actor's Docker configuration and
follow
[daemon discovery and scoped cleanup](../../../docs/development/cloud-docker.md).
A failure at `/var/run/docker.sock` alone does not prove the actor daemon is
down.

[Back to backend](../README.md)
