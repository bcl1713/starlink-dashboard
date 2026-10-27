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

## Live flight detection and recording

Mission Planner's **Flight recording** panel shows detector and telemetry
capture readiness separately. `GET /api/flight-recording/status` exposes the
same status; `GET /health` includes it as `flight_recording` and is degraded if
live recording or detection is unavailable. An HTTP 200 from `/health` alone is
not proof of recording readiness. Overview retains its brief movement
uncertainty treatment; detailed storage diagnostics belong in mission planning.

Both configuration methods (POST and PUT `/api/config`) reconcile the actual
live/simulation source and flight runtime. Entering live initializes it without
a restart. Simulation pauses live inference/collection, interrupts pending
dwell, and retains confirmed events and archives. Returning to live retains
mission/leg identity and history. Simulated observations never become
operational samples.

Failed initialization retries after 5 seconds, then 10, 20, 40 and at most 60
seconds between attempts. The background telemetry loop owns these attempts;
status reads do not create workers. A disabled background loop (a test setting)
requires an explicit tick to recover. Failed sample writes, event processing and
archive maintenance have separate health stages. A raw sample-write failure does
not prevent supported detection; failed event persistence never confirms a new
phase. Recovery cannot recreate unrecorded aircraft observations by itself.

Read-only diagnostics, before any repair or restart:

```sh
docker compose logs --no-color starlink-location | rg 'Configuration loaded|Live recording'
docker compose exec starlink-location sh -c 'id; ls -ld "${FLIGHT_ARCHIVE_ROOT:-/app/data/flight-events}"'
docker compose exec starlink-location sh -c 'ls -l "${FLIGHT_ARCHIVE_ROOT:-/app/data/flight-events}"'
```

Record the deployed image revision, effective startup mode and any later mode
changes. Preserve the original logs and archive files. `storage_path` means the
configured root cannot be used as a directory; `storage_permissions` identifies
an OS permission failure; `database` includes SQLite open/write/corruption
failures; `invalid_policy` means invalid `FLIGHT_DETECTION_POLICY`; `storage`
covers other filesystem failures. Messages omit sensitive raw values and expose
a safe cause, SQLite error name/OS errno when available, action and retry delay.

The ordinary mount is `./data/flight-events:/app/data/flight-events`. Its host
ownership replaces image ownership. The entrypoint prepares only the effective
archive root for appuser (UID 1000), including a custom `FLIGHT_ARCHIVE_ROOT`;
existing database/download file ownership is preserved. Check directory
traversal, write access, existing file ownership, disk capacity and database
health. Do not recursively change retained files, delete a suspect database or
create an empty replacement to make the health check green. Preserve evidence
and arrange a specific repair or consistent backup restoration. Automatic
retries pick up a restored root or corrected policy; changing a container
environment variable still requires the deployment's normal
configuration/recreation procedure.

An export with `archive_runtime_unavailable` and no `telemetry/` members
indicates an absent runtime at capture time. `no_executable_legs` is a healthy
runtime with an empty draft mission. Included captures retain observed
sample/event provenance and labeled gaps. Planning CSVs/altitudes are not
measured movement history; missing export telemetry does not prove the dish or
Prometheus stopped recording. See
[flight event operator guidance](../operations/mission-journal-archive.md#inferred-flight-events-and-reconciliation).
