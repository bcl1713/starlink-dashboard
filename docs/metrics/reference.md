# Metrics reference

This is a selected operational reference for the current checkout, not a promise
that every registered family is populated in every mode. The authoritative
[registry](../../backend/starlink-location/app/core/metrics/prometheus_metrics.py)
and
[updater](../../backend/starlink-location/app/core/metrics/metric_updater.py)
define names, labels, units and publication behavior. Inspect `/metrics` for
actual series. Labeled families may have no samples until a label set is used.

## Current-value gauges

| Metric                                          | Unit / meaning                                                          |
| ----------------------------------------------- | ----------------------------------------------------------------------- |
| `starlink_dish_latitude_degrees`                | Decimal degrees                                                         |
| `starlink_dish_longitude_degrees`               | Decimal degrees                                                         |
| `starlink_dish_altitude_feet`                   | Feet above sea level; there is no `starlink_dish_altitude_meters` gauge |
| `starlink_dish_speed_knots`                     | Knots                                                                   |
| `starlink_dish_heading_degrees`                 | Degrees, 0 north and 90 east                                            |
| `starlink_network_latency_ms_current`           | Round-trip milliseconds                                                 |
| `starlink_network_throughput_down_mbps_current` | Download Mbps                                                           |
| `starlink_network_throughput_up_mbps_current`   | Upload Mbps                                                             |
| `starlink_network_packet_loss_percent`          | Percent, 0–100                                                          |
| `starlink_dish_obstruction_percent`             | Percent, 0–100                                                          |
| `starlink_signal_quality_percent`               | Source-provided signal quality percentage                               |
| `starlink_uptime_seconds`                       | Telemetry environmental uptime value                                    |

These gauges have no exporter-defined `mode` or `status` labels. Unavailable
verified network/obstruction fields publish `NaN`; a zero is not a substitute
for unknown. Composite position families also exist:
`starlink_aircraft_position{dimension="latitude|longitude|altitude"}` and
`starlink_device_location{lat="…",lon="…",altitude="…"}`. Composite altitude
uses the same telemetry feet value. Prefer numeric position gauges for analysis.

## Histograms

| Base family                                | Finite bucket bounds                              | Labels           |
| ------------------------------------------ | ------------------------------------------------- | ---------------- |
| `starlink_network_latency_ms`              | 20, 40, 60, 80, 100, 150, 200, 500 ms             | `mode`, `status` |
| `starlink_network_throughput_down_mbps`    | 50, 100, 150, 200, 250, 300 Mbps                  | `mode`, `status` |
| `starlink_network_throughput_up_mbps`      | 10, 20, 30, 40, 50 Mbps                           | `mode`, `status` |
| `starlink_metrics_scrape_duration_seconds` | 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5 s | None             |

Each histogram exports `_bucket` (with `le`, including `+Inf`), `_sum` and
`_count` series. The base name itself is not an instantaneous sample. The
collection-duration family measures ordinary background metric-update work, not
Prometheus HTTP request duration or an end-to-end scrape timeout.

Network histograms observe only individually available measurements. Status is
computed from verified latency and packet loss in
[labels.py](../../backend/starlink-location/app/core/labels.py), in this order:

- `unknown`: either input is unavailable.
- `excellent`: latency < 50 ms **and** packet loss < 1%.
- `good`: latency < 100 ms **and** packet loss < 5%.
- `degraded`: latency < 150 ms **and** packet loss < 10%.
- `poor`: otherwise.

Configured operation supplies `mode` (`simulation` or `live`); calls without a
configuration use `unknown`. Status is a telemetry classification, independent
of mission communication-plan states.

## Navigation and mission gauges

| Family                                                                                                               | Exporter labels                                               |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `starlink_eta_poi_seconds`, `starlink_distance_to_poi_meters`                                                        | `name`, `category`, `eta_type` (`anticipated` or `estimated`) |
| `starlink_route_progress_percent`, `starlink_current_waypoint_index`                                                 | `route_name`                                                  |
| `starlink_route_has_timing_data`, `starlink_route_total_duration_seconds`                                            | `route_name`                                                  |
| `starlink_route_departure_time_unix`, `starlink_route_arrival_time_unix`, `starlink_route_segment_count_with_timing` | `route_name`                                                  |
| `starlink_eta_to_waypoint_seconds`, `starlink_distance_to_waypoint_meters`                                           | `route_name`, `waypoint_name`                                 |
| `starlink_route_segment_speed_knots`                                                                                 | `route_name`, `segment_index`                                 |
| `mission_active_info`                                                                                                | `mission_id`, `route_id`                                      |
| `mission_phase_state`, `mission_next_conflict_seconds`, `mission_timeline_generated_timestamp`                       | `mission_id`                                                  |
| `mission_comm_state`                                                                                                 | `mission_id`, `transport`                                     |
| `mission_degraded_seconds`, `mission_critical_seconds`                                                               | `mission_id`                                                  |

POI ETA and distance units are seconds and meters. Flight phase and ETA-mode
families also exist without exporter labels: `starlink_flight_phase` uses 0
pre-departure, 1 in-flight, 2 post-arrival; `starlink_eta_mode` uses 0
anticipated, 1 estimated. Route and mission series depend on active data and
timing. Planning values describe the plan, not measured link performance.

Transient mission gauges publish only the current mission/route owner.
Switching, deactivation and deletion remove old label children rather than
retaining stale active values or manufacturing empty-route zeros. POI/route
frame replacement likewise removes old names, categories and ETA modes. Removal
stops new samples; retained Prometheus history remains available. See the
[lifecycle inventory and verification](../performance/perf-393-metric-lifecycle.md).

## Metadata and instrumentation limitations

`starlink_service_info{version,mode}` and `starlink_mode_info{mode}` are
metadata gauges. Do not treat a metadata label as proof of dish connectivity or
release provenance. `starlink_metrics_last_update_timestamp_seconds` tracks
successful ordinary background metric updates, not HTTP scrapes or guaranteed
paced-replay progress. `starlink_metrics_generation_errors_total` counts
failures in that update path.

The registry also declares connection/outage/thermal event counters, dish
uptime/status gauges, and `simulation_errors_total`. Their declaration alone
does not establish that all acquisition paths update them. They are not a
validated availability/SLA calculation. `simulation_updates_total` currently
increments in the shared telemetry updater, including live updates; its name
must not be used as proof of simulation mode or a fixed 10 Hz cadence.

See [overview queries](overview.md) and
[health semantics](health-monitoring.md).
