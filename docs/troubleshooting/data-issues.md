# Data and storage troubleshooting

Inspect actual container mounts before diagnosing missing files:

```bash
docker compose ps -q starlink-location
docker compose exec starlink-location ls -ld /data /data/routes /data/sim_routes /app/data/missions /app/data/settings
docker compose exec starlink-location ls -l /data/pois.json
```

Use `docker inspect <container-id>` to resolve project-prefixed named volumes
and bind directories. POIs normally live in `/data/pois.json`, not under the
backend source tree. Routes and simulation routes have separate nested mounts.
See the complete [storage map](../setup/configuration/storage-configuration.md).

If data disappeared after redeployment, check whether the Compose project name,
volume identity, host bind path, or deployment profile changed. `down --volumes`
removes named-volume data. Do not create an unprefixed replacement volume while
trying to inspect an existing installation.

For permission or JSON errors, preserve the original file and logs before
repair. Verify the service user's ownership and write access on the actual
mounted location; do not use world-writable permissions or overwrite the file
with `[]`. Restore a known-good consistent backup when needed.

For route, POI or mission errors, inspect the API response in Mission Planner
and the backend logs. Use the current interactive schema at
<http://localhost:8000/docs> for request and response shapes; older examples
that assume bare POI arrays or default speed fallbacks do not cover every live
freshness case. Upload failures have separate
[size-limit diagnostics](../setup/configuration/mission-package-upload-limits.md).
