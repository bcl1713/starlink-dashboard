# System requirements

Use Git, Docker Engine or Docker Desktop, and Docker Compose v2. Verify the
installed daemon and Compose implementation rather than relying on an old
minimum-version claim:

```bash
git --version
docker version
docker info
docker compose version
```

Keep the configured Docker context and `DOCKER_HOST`. In the managed cloud
runtime, follow [cloud Docker discovery](../development/cloud-docker.md);
failure at `/var/run/docker.sock` alone does not establish a daemon outage.

Allow enough memory and disk for image builds, scientific Python dependencies,
weather products, and retained telemetry. The GFS worker alone has a 1 GiB
memory limit and one CPU; the complete stack and builds require additional
resources. No fixed RAM or disk minimum is validated for every mission size and
retention policy. Measure usage with `docker stats --no-stream` and
`docker system df`.

Default host ports are 5173 (Mission Planner), 8000 (backend), and 9090
(Prometheus). The GFS worker publishes no port. Avoid exposing unauthenticated
APIs or metrics publicly; select access rules for your deployment.

Simulation needs no Starlink hardware. Live mode needs a reachable dish gRPC
endpoint, normally `192.168.100.1:9200`. Internet access is required for initial
image builds and enabled external data sources; simulation telemetry itself can
run offline. See [live setup](configuration/live-mode/setup.md).
