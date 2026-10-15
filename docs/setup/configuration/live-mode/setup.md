# Live mode setup

Use a Starlink dish reachable from the backend container, normally at
`192.168.100.1:9200`. In the local `.env` set:

```dotenv
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1
STARLINK_DISH_PORT=9200
```

Apply with `./scripts/compose.sh up -d starlink-location`. Explicit
`STARLINK_MODE` takes precedence over legacy `SIMULATION_MODE`.

The bridge network needs a working route to the dish subnet. The supplied
`dish.starlink` host mapping does not establish routing. Verify network access
from the backend container; host access alone does not prove container access.
Do not assume host networking is interchangeable with the supplied bridge:
service aliases, host ports, and platform support change.

```bash
curl --fail --max-time 10 http://localhost:8000/health

docker compose exec starlink-location python -c \
  'import os,socket; s=socket.create_connection((os.getenv("STARLINK_DISH_HOST","192.168.100.1"),int(os.getenv("STARLINK_DISH_PORT","9200"))),timeout=5); s.close()'
```

TCP reachability only establishes an open port; successful gRPC telemetry is a
separate check. In `/health`, confirm `mode: "live"` and `dish_connected: true`.
The server can be healthy while awaiting a dish connection. Live mode does not
fall back to simulated data. Failed acquisition yields no new valid sample;
check freshness and connectivity before trusting old displayed values.

See [live troubleshooting](../../../troubleshooting/connectivity/live-mode.md)
and the separate
[Portainer rollout gate](../../../deployment/portainer-ghcr.md#live-rollout-gate)
for that managed deployment.
