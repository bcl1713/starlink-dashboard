# Flight Status & ETA Modes Migration Notes

**Version:** 0.1.0  
**Last Updated:** 2025-11-05  

This document summarizes operational considerations when adopting the new flight-phase manager and dual ETA mode features introduced in the ETA Timing Modes initiative.

---

## Backward Compatibility

- **API schema additions only:** Existing endpoints keep their previous fields. New metadata (`flight_phase`, `eta_mode`, `is_pre_departure`, `time_until_departure_seconds`, `eta_type`) extend responses but do not break older clients.
- **Metric labels:** `starlink_eta_poi_seconds` and `starlink_distance_to_poi_meters` gained an `eta_type` label. Update any Prometheus alerting rules or Grafana queries that rely on exact label sets.
- **Route manager behaviour:** Activating a new route now resets the global flight state to `pre_departure`. Workflows that relied on persisting `in_flight` status across route swaps should trigger a manual departure after activation.
- **Simulation speed smoothing:** During pre-departure scrapes, the metrics exporter seeds a default cruise speed to keep ETAs non-negative. Consumers expecting `-1` for “no ETA” should now check the `flight_phase` field instead.

---

## Deployment Checklist

1. **Rebuild containers**
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```
2. **Verify health & docs**
   ```bash
   curl http://localhost:8000/health | jq
   curl http://localhost:8000/docs
   ```
3. **Check Prometheus labels**
   ```bash
   curl http://localhost:8000/metrics | grep starlink_eta_poi_seconds
   ```
4. **Confirm Grafana dashboards**  
   Hard refresh overview & fullscreen dashboards to ensure PLANNED/LIVE badges render correctly.

---

## Recommended Follow-Up

- Update any custom dashboards or alert rules to display `eta_type` and `flight_phase`.
- Communicate the new `/api/flight-status/depart` and `/api/flight-status/arrive` manual overrides to operations teams.
- Schedule regression tests for integrations that parse `/api/pois/etas` to ensure the additional metadata is handled gracefully.
