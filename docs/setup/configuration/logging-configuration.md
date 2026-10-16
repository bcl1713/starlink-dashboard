# Logging configuration

The backend reads `LOG_LEVEL` (default `INFO`), `JSON_LOGS` (default `true`),
and optional `LOG_FILE` at startup. Supported standard levels include `DEBUG`,
`INFO`, `WARNING`, `ERROR`, and `CRITICAL`. For temporary diagnosis, add
`LOG_LEVEL=DEBUG` to `.env` and recreate the backend:

```bash
./scripts/compose.sh up -d starlink-location
docker compose logs --tail=200 starlink-location
docker compose logs --tail=200 gfs-worker prometheus mission-planner
```

Set `JSON_LOGS=false` for text application logs. These options do not change
Prometheus or Nginx logging. Restore the desired level after diagnosis and avoid
sharing secrets or sensitive mission data in captured logs.

Docker log rotation depends on the daemon/logging driver; this Compose file does
not set a rotation policy. If required, configure supported driver options such
as `max-size` and `max-file` in your deployment and recreate affected
containers.
