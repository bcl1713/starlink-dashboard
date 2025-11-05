# Flight Status Operations Guide

**Version:** 0.1.0  
**Last Updated:** 2025-11-05  
**Status:** Draft – Flight phase management live in `feature/eta-route-timing`

This guide documents how the flight-state subsystem tracks aircraft progress, switches ETA modes, and surfaces information across APIs, metrics, and dashboards.

## Table of Contents

1. [Overview](#overview)  
2. [Quick Start](#quick-start)  
3. [State Machine](#state-machine)  
4. [Automatic Detection](#automatic-detection)  
5. [Manual Overrides](#manual-overrides)  
6. [Shared Metadata](#shared-metadata)  
7. [Metrics & Observability](#metrics--observability)  
8. [Grafana Dashboards](#grafana-dashboards)  
9. [API Reference Highlights](#api-reference-highlights)  
10. [Troubleshooting](#troubleshooting)  
11. [Glossary](#glossary)

---

## Overview

The flight-state manager provides a single source of truth for where the aircraft is in its mission timeline. It controls:

- The active **flight phase** (`pre_departure`, `in_flight`, `post_arrival`)
- The current **ETA mode** (`anticipated` vs `estimated`)
- Actual departure/arrival timestamps alongside the planned schedule
- Countdown information for dashboards and Prometheus consumers
- Consistent propagation of status metadata to routes, POIs, metrics, and health endpoints

The manager is thread-safe, persists state across API calls, and reacts to both automatic telemetry checks and manual operator commands.

---

## Quick Start

1. **Reset state (optional)**
   ```bash
   curl -X POST http://localhost:8000/api/flight-status
   ```
2. **Trigger departure**
   ```bash
   curl -X POST http://localhost:8000/api/flight-status/depart -d '{"reason":"manual-test"}' -H "Content-Type: application/json"
   ```
3. **Inspect status**
   ```bash
   curl http://localhost:8000/api/flight-status | jq
   ```
4. **Trigger arrival**
   ```bash
   curl -X POST http://localhost:8000/api/flight-status/arrive -d '{"reason":"manual-test"}' -H "Content-Type: application/json"
   ```
5. **Review Prometheus metrics**
   ```bash
   curl http://localhost:8000/metrics | grep starlink_flight_
   ```

---

## State Machine

```
PRE_DEPARTURE --(speed >= threshold OR manual depart)--> IN_FLIGHT
IN_FLIGHT --(distance_to_destination < 100 m for 60 s OR manual arrive)--> POST_ARRIVAL
POST_ARRIVAL --(manual reset OR route change)--> PRE_DEPARTURE
```

- **PRE_DEPARTURE:** Planned timeline; ETAs use anticipated mode.
- **IN_FLIGHT:** Aircraft airborne; ETAs use estimated mode.
- **POST_ARRIVAL:** Mission complete; ETA mode remains estimated until reset.

The manager stores these bindings:

| Field | Description |
|-------|-------------|
| `phase` | Current `FlightPhase` enum |
| `eta_mode` | Current `ETAMode` enum |
| `scheduled_departure_time` / `scheduled_arrival_time` | Planned timestamps (if provided in KML) |
| `actual_departure_time` / `actual_arrival_time` | Set on transitions |
| `active_route_id` / `active_route_name` | Connected route context |
| `time_until_departure_seconds` | Auto-computed countdown (≥0) |

---

## Automatic Detection

Automatic transitions run inside the telemetry loop (`update_metrics_from_telemetry`) and the flight-state manager:

| Transition | Trigger | Implementation Notes |
|------------|---------|----------------------|
| PRE_DEP → IN_FLT | Smoothed speed ≥ 40 kn (configurable) | `FlightStateManager.check_departure(speed_knots)` |
| IN_FLT → POST_ARR | Final waypoint within 100 m for ≥60 s and speed < 5 kn | Uses `RouteETACalculator.get_route_progress()` |
| Route change | Activated route differs from stored route | `route_manager.activate_route` calls `update_route_context()` |

Automatic detection is disabled in test contexts when `STARLINK_DISABLE_BACKGROUND_TASKS=1`, but manual endpoints still function for deterministic testing.

---

## Manual Overrides

Operators can override the state machine through dedicated endpoints:

| Endpoint | Payload | Effect |
|----------|---------|--------|
| `POST /api/flight-status` | Optional `{"reason": "...", "timestamp": "ISO8601"}` | Resets to pre-departure and clears actual timestamps |
| `POST /api/flight-status/depart` | Optional `{"timestamp": "...", "reason": "..."}` | Forces departure; assigns provided timestamp or current UTC; switches ETA mode to estimated |
| `POST /api/flight-status/arrive` | Optional `{"timestamp": "...", "reason": "..."}` | Forces arrival; locks arrival timestamp; keeps ETA mode estimated |

Manual transitions broadcast to API consumers immediately and are mirrored in Prometheus metrics on the next scrape.

---

## Shared Metadata

Flight-state fields are propagated through the stack:

- **Routes API:** `/api/routes` list/detail responses include `flight_phase`, `eta_mode`, `active_route_id`, and timing metadata.
- **POI ETAs:** `/api/pois/etas` entries expose `eta_type`, `flight_phase`, `is_pre_departure`, and the numeric `eta_seconds`.
- **Health Endpoint:** `/health` reports phase, ETA mode, countdown, active route identifiers, and a human-readable status message.
- **Prometheus:** `starlink_flight_phase`, `starlink_eta_mode`, and `starlink_time_until_departure_seconds` are updated on each telemetry cycle or metrics scrape.
- **Grafana dashboards:** PLANNED/LIVE badges, departure countdown stat, and POI tables derive from the same shared values.

---

## Metrics & Observability

| Metric | Description | Labels/Values |
|--------|-------------|---------------|
| `starlink_flight_phase` | Numeric encoding of current phase (0/1/2) | No labels |
| `starlink_eta_mode` | Numeric encoding of ETA mode (0 anticipated, 1 estimated) | No labels |
| `starlink_time_until_departure_seconds` | Countdown until scheduled or actual departure | No labels |
| `starlink_eta_poi_seconds` | POI ETA gauge | `name`, `category`, `eta_type` |
| `starlink_distance_to_poi_meters` | POI distance gauge | `name`, `category`, `eta_type` |

Scrape considerations:

- When background updates are disabled, `/metrics` calls inject default cruise speed to keep pre-departure ETAs non-negative.
- If the flight-state manager is unavailable, the exporter falls back to estimated mode and logs a warning.

---

## Grafana Dashboards

The following panels consume flight-state data:

- **Overview Dashboard**
  - *Departure Countdown Stat* – driven by `starlink_time_until_departure_seconds`
  - *Flight Status Badges* – switch between PLANNED and LIVE based on `eta_mode`
- **Fullscreen Overview**
  - Map legend indicates mode and phase
  - POI quick reference table highlights anticipated vs estimated ETAs
- **POI Management Dashboard**
  - Lists `eta_type`, `flight_phase`, and countdown columns for operations teams

After deploying new dashboards, run:
```bash
docker compose restart grafana
```
to reload provisioning changes.

---

## API Reference Highlights

- `GET /api/flight-status` – canonical snapshot; includes planned and actual timestamps, countdown, current phase, ETA mode, and active route metadata.
- `GET /api/pois/etas` – returns POI list with enriched fields; consumers should honour `eta_type` and `is_pre_departure` to avoid filtering pre-flight POIs.
- `GET /api/routes` / `GET /api/routes/{id}` – embed flight-state metadata alongside route timing profile.
- `GET /health` – quick check for dashboards/alerting; `dish_connected` remains for live mode, while `mode` clarifies simulation or live.

Additions to OpenAPI descriptions (in FastAPI docstrings) should reference the new fields for clarity.

---

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| Flight phase stuck in `pre_departure` | Speed never crosses threshold | Trigger `/api/flight-status/depart` with `{"reason":"manual override"}` or check telemetry smoothing window |
| `eta_type` labels missing from Prometheus | Metrics scraped before any POIs loaded | Create at least one POI or invoke `/api/pois` seed fixtures |
| Countdown negative or inaccurate | Scheduled departure earlier than current UTC | Reset flight status or update route timing profile |
| Grafana still shows PLANNED after departure | Dashboard cache stale | Hard refresh dashboard or confirm Prometheus scrape frequency |

---

## Glossary

- **FlightPhase** – Enum representing lifecycle stage (`PRE_DEPARTURE`, `IN_FLIGHT`, `POST_ARRIVAL`).
- **ETAMode** – Enum representing calculation strategy (`ANTICIPATED`, `ESTIMATED`).
- **Timing Profile** – Parsed KML metadata containing planned timestamps and segment speeds.
- **Countdown** – Seconds until planned or actual departure; exposed via API and metrics.

---

For further architectural background see `dev/completed/eta-timing-modes/ETA-ARCHITECTURE.md` and `docs/ROUTE-TIMING-GUIDE.md`.
