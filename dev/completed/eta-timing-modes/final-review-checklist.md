# Final Review Checklist – ETA Timing Modes

**Version:** 0.1.0  
**Last Updated:** 2025-11-05 (Session 33)

This checklist tracks the remaining verifications required to close Phase 8 Task 8.7.

---

## 1. Code Review

- [x] Confirm no lingering TODO/FIXME markers in new modules (`flight_state_manager`, augmented tests, metrics exporters).
  - Verified via `rg --line-number "TODO|FIXME"` against `flight_state_manager.py`, `metrics_export.py`, and ETA service modules (no matches).
- [ ] Re-run static analysis / lint where available (pending tooling setup).
- Notes: Prior sessions already integrated timezone fixes and concurrency guards; ensure reviewers focus on ETA mode switching and metrics exporter resilience.

## 2. Documentation Review

- [x] Route timing guide updated with ETA modes (`docs/ROUTE-TIMING-GUIDE.md`).
- [x] Flight status operations guide published (`dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md`).
- [x] Migration notes captured (`dev/completed/eta-timing-modes/flight-status-migration-notes.md`).
- [x] Update high-level design doc (`docs/design-document.md`) with flight-state section.

## 3. Test Coverage

- [x] `.venv/bin/python -m pytest --cov=app --cov-report=term backend/starlink-location/tests -q` (530 passed / 4 skipped / 1 warning; total coverage 79 %).
- [x] Evaluate low-coverage modules (`eta_cache`, `route_eta_calculator`, `pois` API) for possible quick wins before release.
  - Added `tests/unit/test_eta_cache_service.py` to exercise ETACache keying, TTL cleanup, and ETAHistoryTracker accuracy.
  - Added `tests/unit/test_route_eta_calculator_service.py` covering projection, waypoint/location ETAs, and progress calculations.
- Notes: ETA timing additions exceed 95 % coverage; overall gap now dominated by legacy route ETA utilities.

## 4. Performance Benchmarks

- [x] `tests/unit/test_performance_metrics.py` validates ETA throughput and state-manager overhead (<50 ms per POI; <1 ms `check_departure`).
- [ ] Optional: Re-run benchmarks on target hardware if production differs from dev environment.

## 5. Security & Observability

- [x] Confirm Prometheus scrapes in staging/CI reflect new `eta_type` label (manual scrape recommended).
  - Validated via `.venv/bin/python -m pytest backend/starlink-location/tests/integration/test_eta_modes.py::test_metrics_exposes_eta_type_labels -vv` (pass, labels present).
  - Captured live sample inside Docker: `docker compose exec starlink-location sh -c "curl -s http://localhost:8000/metrics | grep 'starlink_eta_poi_seconds{category=\"test\",eta_type=\"estimated\",name=\"PromScrapeTest\"}'"` (label emitted).
- [x] Ensure no sensitive data leaks in new logs (review `FlightStateManager` logs & migration notes).
  - Reviewed `FlightStateManager` logging—state transitions and route identifiers only, no telemetry/PII emitted.

---

### Outstanding Actions

1. Optional: Mirror the Docker scrape sample in staging to confirm environment parity before release.

Once the above items are addressed, Task 8.7 can be marked ✅.
