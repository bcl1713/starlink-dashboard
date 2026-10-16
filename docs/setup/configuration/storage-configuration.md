# Storage and retention

The root Compose profile persists these categories:

| Storage                                                      | Container path / purpose                                   |
| ------------------------------------------------------------ | ---------------------------------------------------------- |
| `./data/missions`                                            | `/app/data/missions`, mission records                      |
| `./data/settings`                                            | `/app/data/settings`, operator preferences                 |
| `./data/satellites`, `./data/sat_coverage`, `./data/orbital` | Matching `/app/data/` paths, satellite and orbital data    |
| `route_data`                                                 | `/data/routes`                                             |
| `sim_route_data`                                             | `/data/sim_routes`                                         |
| `poi_data`                                                   | `/data`, including `pois.json`                             |
| `prometheus_data`                                            | `/prometheus`, telemetry database                          |
| `gfs_products`                                               | `/app/data/gfs`, worker writes and API reads               |
| `gfs_mailbox`                                                | `/app/data/gfs-mailbox`, weather control/admission records |

Named volumes receive the Compose project prefix; do not assume their engine
names are the logical keys above. Inspect actual mounts with
`docker compose ps -q` and `docker inspect <container-id>`. The nested route
mounts are separate from the parent POI volume and need separate backups.

Set `PROMETHEUS_RETENTION=30d` (or another supported duration) in `.env` and run
`./scripts/compose.sh up -d prometheus` to change retained history. Storage use
depends on time-series cardinality, active missions, sample rate, WAL, and
compaction; an old 45-series estimate is not a capacity guarantee. Inspect
actual usage before selecting retention.

`docker compose down` preserves named volumes and bind-mounted files. Keep the
same project name on subsequent starts to reuse them. `down --volumes` deletes
named-volume data; do not use it for an installation you intend to retain.
Retain GFS mailbox/products across restarts to preserve quotas and admission
clocks. Back up every relevant bind directory and resolved named volume using a
consistent stopped-service backup or the database's snapshot procedure. Never
reset a corrupt JSON file before preserving it for diagnosis and recovery.

Portainer uses three supplied host-path categories and named GFS volumes
instead; see its [deployment runbook](../../deployment/portainer-ghcr.md).

## Observed flight telemetry archives

Live mode stores the event ledger, candidate history pins, raw rolling buffer,
capture revisions, and sealed CSV ZIPs under `data/flight-events` by default.
Local Compose mounts `data/flight-events` at `/app/data/flight-events`;
production Compose already persists the enclosing `/app/data` directory. Set
`FLIGHT_ARCHIVE_ROOT` only to a backend-owned persistent volume path. Back up
this directory with mission data; deleting download jobs does not delete source
archives. Sealed archives have no automatic retention expiry in this release.

The rolling source buffer retains at least 35 minutes. Candidate off-blocks
history and open captures pin their required earlier observations. Capture runs
from 30 minutes before off-blocks until 30 minutes after first confirmed
destination parking, including DV offload. Repositioning after that park does
not change the automatic boundary. Explicit operator corrections produce new
revisions. Intermediate operational stops remain inside the planned leg.

`FLIGHT_DETECTION_POLICY` accepts a JSON object overriding the documented
engineering policy fields in the flight-events evidence report. Defaults are not
field-calibrated aircraft operating limits. Missing evidence requires manual
confirmation. Startup while moving does not invent a departure time.

Prometheus recovery uses `STARLINK_PROMETHEUS_URL` and selects only the source
identified by `FLIGHT_ARCHIVE_PROMETHEUS_INSTANCE` (default
`starlink-location:8000`) and `FLIGHT_ARCHIVE_PROMETHEUS_JOB` (default
`starlink-location`). Raw samples also require same-scrape live-mode provenance.
Set these selectors when changing scrape targets; never combine aircraft
sources. Recovery retries are persisted and bounded. Gaps remain visible when
history was never collected or has expired. Cached public-egress labels are
last-known proxy information with unknown source freshness, not physical RF
gateway evidence.

Mission recording controls create or correct observed events and classify a
parking stop as intermediate or destination completion. The application relies
on its existing restricted-access operator boundary; it does not authenticate
individual operator identities. Event notes do not establish authentication.
Storage failures leave operational metric publication running and are logged.

Archive size grows with metric series and mission duration. Monitor free space
and archive health, and manage sealed archive retention through your existing
backup policy. A full disk or missing volume can prevent capture; it cannot be
repaired by silently substituting zero measurements.
