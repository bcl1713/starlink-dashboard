# Installation verification

From the installation directory, with services already started:

```bash
docker compose ps
curl --fail --max-time 10 http://localhost:8000/health
curl --fail --max-time 10 http://localhost:5173/api/status
curl --fail --max-time 10 http://localhost:9090/-/ready
curl --fail --max-time 10 http://localhost:9090/api/v1/targets
curl --fail --max-time 10 http://localhost:8000/metrics
```

Use your configured host ports if different. Open <http://localhost:5173> and
confirm Overview loads; inspect the Prometheus target `starlink-location:8000`
for `health: "up"`. Backend health reports mode and startup information. In live
mode inspect `dish_connected` separately: a healthy HTTP server may still be
waiting for its dish. Simulation does not include that live-only field.

A simulation position normally changes at the configured update cadence, except
when replay or route completion deliberately freezes it. Missing history can
mean Prometheus has only just started or no valid live samples are available; it
does not necessarily mean the frontend failed.

If a check fails, use [troubleshooting](../troubleshooting/README.md).
