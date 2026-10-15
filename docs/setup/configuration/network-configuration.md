# Network configuration

The local Compose bridge network connects Mission Planner, the backend,
Prometheus and the GFS worker. Mission Planner serves at host port 5173 and
proxies `/api/...` to `starlink-location:8000`. Prometheus scrapes that backend
service name; host port changes do not change the internal target.

Set `STARLINK_LOCATION_PORT` and `PROMETHEUS_PORT` in `.env` to resolve host
port conflicts, then run `./scripts/compose.sh up -d`. Port 5173 is specified
directly in Compose. The worker has no public port. Publish only the services
your users need; this stack does not configure authentication or TLS for exposed
APIs.

Live telemetry needs outbound routing from the backend container to the dish
host and gRPC port, normally `192.168.100.1:9200`. The `dish.starlink`
extra-hosts entry adds a name mapping; it does not create a route or bypass
firewalls. Test from the container's network context. See
[live setup](live-mode/setup.md).

For API checks use host `curl`, or `docker compose exec starlink-location curl`.
The Prometheus image is not a general diagnostic image and should not be assumed
to provide curl or ping. Do not switch to host networking casually: it changes
port and service-name behavior and is platform dependent.
