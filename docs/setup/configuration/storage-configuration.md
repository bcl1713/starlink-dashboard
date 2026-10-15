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
