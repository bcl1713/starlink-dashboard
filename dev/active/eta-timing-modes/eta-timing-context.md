# ETA Timing Modes - Implementation Context

**Last Updated:** 2025-11-04 09:05 UTC
**Phase:** 6/8 - Grafana Dashboards ✅ COMPLETE
**Status:** Ready for Phase 7 (Unit Tests)

## Current Implementation State

### ✅ COMPLETE: Phases 1-6

**Phase 1:** Data Models (FlightPhase, ETAMode enums)
**Phase 2:** Flight State Manager (singleton, thread-safe)
**Phase 3:** Dual-Mode ETA Calculation (anticipated/estimated)
**Phase 4:** API Endpoints (/api/flight-status, POI ETAs)
**Phase 5:** Prometheus Metrics (flight_phase, eta_mode gauges)
**Phase 6:** Grafana Dashboard Panels (4 panels, 4 dashboards updated)

### Key Architecture Decisions

1. **Flight Phase Detection:**
   - Speed-based departure: 50 knots sustained for 10 seconds
   - Arrival: 100m distance + 60-second dwell time
   - Rationale: Works independently of route/schedule

2. **Speed Blending Formula:**
   - `blended_speed = (current_speed + expected_speed) / 2`
   - Applied to current segment only; future segments use planned speeds
   - Provides balance between real-time and planned speeds

3. **Metric Labels:**
   - Single `starlink_eta_poi_seconds` metric with `eta_type` label
   - Avoids metric explosion; backward compatible

4. **Dashboard Panels:**
   - Flight Phase: stat panel with emoji indicators (🚁 🛫 🛬)
   - ETA Mode: stat panel showing ANTICIPATED/ESTIMATED
   - Timeline: markdown visualization of phase progression
   - Color-Coded ETAs: time series with blue (anticipated) and green (estimated)

### Session 6 Changes (Grafana Phase)

**Files Modified:**
- `eta_calculator.py:194-198` - Fixed ETA fallback logic (now uses distance-based calculation)
- `overview.json` - Added 3 panels (ids 204-206)
- `fullscreen-overview.json` - Added 3 panels (ids 205-207)
- `network-metrics.json` - Added 1 panel (id 105)
- `poi-management.json` - Added 1 panel (id 305)

**Files Created:**
- `PHASE-6-DESIGN.md` - Comprehensive design documentation
- `panel-definitions.json` - JSON panel templates for reference
- `PHASE-6-SUMMARY.md` - Implementation summary

### Important Implementation Details

**ETA Calculation Logic:**
- Anticipated mode: Uses flight plan times from route waypoints
- Estimated mode: Uses current speed blended with expected segment speeds
- Fallback: Uses distance/default_speed when no route data available
- Special case: Returns -1 when aircraft speed < 0.5 knots (stationary)

**Flight Status API:**
```
GET /api/flight-status → {phase, eta_mode, departure_time, arrival_time}
POST /api/flight-status/transition → Manual phase transition
POST /api/flight-status → Reset to PRE_DEPARTURE
```

**Prometheus Metrics:**
- `starlink_flight_phase` (0=pre, 1=in, 2=post)
- `starlink_eta_mode` (0=anticipated, 1=estimated)
- `starlink_flight_departure_time_unix` (timestamp)
- `starlink_flight_arrival_time_unix` (timestamp)
- `starlink_eta_poi_seconds{eta_type="..."}` (labeled)

## Known Issues & Behaviors

### ETA Display Shows -1
**Status:** WORKING AS DESIGNED ✅

The aircraft is in PRE_DEPARTURE phase with 0 speed. The -1 value is correct:
- `calculate_eta()` returns -1 when speed < 0.5 knots (line 134)
- This indicates "no valid ETA - aircraft stationary"
- Once aircraft reaches 50+ knots, it transitions to IN_FLIGHT and ETAs become positive

### Route-Aware ETAs
- Only work when POI name matches waypoint name on active route
- Fall back to distance-based calculation otherwise
- This is intentional - ensures robustness

## Testing Strategy (Phase 7)

**Unit Tests Required:**
1. FlightStateManager (15+ tests)
   - Speed-based departure detection
   - Arrival detection logic
   - Manual phase transitions
   - State persistence

2. ETACalculator Dual-Mode (20+ tests)
   - Anticipated mode with route timing
   - Estimated mode with speed blending
   - Fallback calculations
   - Edge cases (zero speed, very far POIs)

3. Integration Tests
   - Full flight phase progression
   - Mode switching on phase change
   - Metric updates on state change

## Next Immediate Tasks

1. ✅ **Commit Phase 6** - Ready to commit
2. ⏳ **Phase 7** - Implement unit tests
3. ⏳ **Phase 8** - Update documentation

## References

- Design doc: `/dev/active/eta-timing-modes/PHASE-6-DESIGN.md`
- Panel templates: `/dev/active/eta-timing-modes/panel-definitions.json`
- Session notes: `/SESSION-NOTES.md`
- Architecture doc: `dev/active/eta-timing-modes/ETA-ARCHITECTURE.md`

## Docker & Services Status

- Backend: http://localhost:8000 ✅
- Grafana: http://localhost:3000 ✅
- Prometheus: http://localhost:9090 ✅
- All containers healthy and running
