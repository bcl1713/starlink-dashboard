# Environment variables

These defaults describe the root local Compose profile. Portainer supplies an
explicit subset through its separate template; adding a local `.env` key does
not add it to a Portainer service.

| Variable                             | Default                  | Effect                                                                              |
| ------------------------------------ | ------------------------ | ----------------------------------------------------------------------------------- |
| `STARLINK_MODE`                      | `simulation`             | `simulation` or `live`                                                              |
| `SIMULATION_MODE`                    | unset                    | Legacy boolean; explicit `STARLINK_MODE` wins                                       |
| `STARLINK_DISH_HOST`                 | `192.168.100.1`          | Dish IP/hostname in live mode                                                       |
| `STARLINK_DISH_PORT`                 | `9200`                   | Dish gRPC port                                                                      |
| `STARLINK_LOCATION_PORT`             | example: `8000`          | Required host-port substitution for backend; internal port stays 8000               |
| `PROMETHEUS_PORT`                    | example: `9090`          | Required host-port substitution; internal port stays 9090                           |
| `PROMETHEUS_RETENTION`               | example: `1y`            | Prometheus stored-history duration                                                  |
| `STARLINK_PROMETHEUS_URL`            | `http://prometheus:9090` | Backend history-query target                                                        |
| `STARLINK_HISTORY_WINDOW_SECONDS`    | `1800`                   | Initial Overview history lookback; persisted choice wins                            |
| `VITE_OVERVIEW_HISTORY_POLL_SECONDS` | `1`                      | Frontend build argument; supported 1s default or 5s rollback; invalid input uses 5s |
| `LOG_LEVEL`                          | `INFO`                   | Backend application log level                                                       |
| `JSON_LOGS`                          | `true`                   | Structured backend logs; `false` selects text                                       |
| `LOG_FILE`                           | unset                    | Optional backend log path; provision writable persistent storage if used            |
| `STARLINK_CONFIG`                    | bundled `config.yaml`    | Alternate YAML path inside the backend container                                    |

Mission Planner's local host port is fixed at 5173 in Compose. Backend YAML
settings can be overridden with `STARLINK_` names, for example
`STARLINK_UPDATE_INTERVAL_SECONDS=2.0` or
`STARLINK_ROUTE_LATITUDE_START=51.5074`. Use fields from the actual YAML/model;
there is no `simulation:` configuration section. `config.yaml` is baked into the
backend image, so editing its source requires rebuilding unless you deliberately
mount an alternate file.

`STARLINK_GROUND_ENTRY_LATITUDE` and `STARLINK_GROUND_ENTRY_LONGITUDE` provide a
paired local simulation/offline GEP. The example supplies 41.2565, -95.9345;
replace or remove both together. They do not prove a live dish ground entry.

The Compose wrapper supplies `ACCEPTANCE_CANDIDATE_SHA` automatically for
builds. Do not use a hand-written revision to bypass the build identity
contract.

Recreate services after environment changes (`./scripts/compose.sh up -d`).
Rebuild Mission Planner after changing its `VITE_` build setting. History query
lookback and polling cadence do not change Prometheus retention.
