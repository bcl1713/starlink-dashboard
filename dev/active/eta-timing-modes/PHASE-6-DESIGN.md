# Phase 6: Grafana Dashboards - Flight Status Visualization

**Date:** 2025-11-04
**Status:** In Progress
**Phase:** 6 of 8

## Overview

Phase 6 adds flight status visualization panels to Grafana dashboards, displaying the new flight phase and ETA mode tracking functionality implemented in Phases 1-5.

## Panel Designs

### Panel 1: Flight Phase Indicator (Stat Panel)
**Location:** Overview and Fullscreen dashboards
**Grid Position:** Top row, left side (h=3, w=6)
**Panel ID:** overview=204, fullscreen=205

**Prometheus Query:**
```promql
starlink_flight_phase
```

**Value Mapping:**
- 0 → "🚁 PRE-DEPARTURE" (orange)
- 1 → "✈️ IN-FLIGHT" (green)
- 2 → "🛬 POST-ARRIVAL" (blue)

**Configuration:**
- Type: `stat`
- Color mode: `background`
- Graph mode: `area`
- Value format: Categorical (via mappings)

### Panel 2: ETA Mode Indicator (Stat Panel)
**Location:** Overview and Fullscreen dashboards
**Grid Position:** Top row, next to Flight Phase (h=3, w=6)
**Panel ID:** overview=205, fullscreen=206

**Prometheus Query:**
```promql
starlink_eta_mode
```

**Value Mapping:**
- 0 → "📋 ANTICIPATED" (blue)
- 1 → "📊 ESTIMATED" (green)

**Configuration:**
- Type: `stat`
- Color mode: `background`
- Graph mode: `area`
- Automatic transition: Phase PRE_DEPARTURE → ANTICIPATED, IN_FLIGHT → ESTIMATED

### Panel 3: Flight Timeline (Stat Panel)
**Location:** Overview and Fullscreen dashboards
**Grid Position:** Below phase indicators (h=4, w=12)
**Panel ID:** overview=206, fullscreen=207

**Prometheus Queries:**
```promql
# Query A: Flight phase (for visual indicator)
starlink_flight_phase

# Query B: Departure timestamp
starlink_flight_departure_time_unix

# Query C: Arrival timestamp
starlink_flight_arrival_time_unix
```

**Display Logic:**
- Shows timeline: PRE-DEPARTURE → IN-FLIGHT → POST-ARRIVAL
- Displays timestamps for departure and arrival when available
- Color progression matches phase: orange → green → blue

**Configuration:**
- Type: `stat` with custom visualization
- Layout: Horizontal timeline representation
- Custom formatting: Show phase names with timestamps

### Panel 4: Color-Coded ETAs (Time Series Panel)
**Location:** Network Metrics and POI Management dashboards
**Grid Position:** Below existing network/POI metrics (h=8, w=24)
**Panel ID:** network=105, poi=305

**Prometheus Queries:**
```promql
# Query A: Anticipated ETAs (blue)
starlink_eta_poi_seconds{eta_type="anticipated"}

# Query B: Estimated ETAs (green)
starlink_eta_poi_seconds{eta_type="estimated"}
```

**Display Configuration:**
- Type: `timeseries`
- Line style: `smooth`
- Fill opacity: `20%`
- Colors:
  - Anticipated ETAs: Blue (#3498db)
  - Estimated ETAs: Green (#2ecc71)
- Legend: Show POI names, display last value and mean
- Tooltip: Shared crosshair

**Label Processing:**
- Extract POI name from labels: `{{name}}`
- Include eta_type in legend: `{{name}} ({{eta_type}})`

## Implementation Plan

### Step 1: Add Panels to Overview Dashboard
1. Add Flight Phase Indicator (id=204)
2. Add ETA Mode Indicator (id=205)
3. Add Flight Timeline (id=206)
4. Update grid positions for existing panels as needed

### Step 2: Add Panels to Fullscreen Overview Dashboard
1. Add Flight Phase Indicator (id=205)
2. Add ETA Mode Indicator (id=206)
3. Add Flight Timeline (id=207)
4. Position in top-right area (kiosk mode optimization)

### Step 3: Add Color-Coded ETA Panel to Network Metrics Dashboard
1. Add ETA Comparison Time Series (id=105)
2. Position below existing network metrics
3. Configure dual-query legend with color distinction

### Step 4: Add Color-Coded ETA Panel to POI Management Dashboard
1. Add ETA Comparison Time Series (id=305)
2. Position below POI metrics
3. Configure for POI-specific visualizations

## Metrics Reference

**Flight Status Metrics (Phase 5):**
- `starlink_flight_phase` - Current flight phase (0=PRE_DEPARTURE, 1=IN_FLIGHT, 2=POST_ARRIVAL)
- `starlink_eta_mode` - Current ETA mode (0=ANTICIPATED, 1=ESTIMATED)
- `starlink_flight_departure_time_unix` - Departure timestamp (seconds)
- `starlink_flight_arrival_time_unix` - Arrival timestamp (seconds)

**ETA Metrics with Labels:**
- `starlink_eta_poi_seconds{name="...", category="...", eta_type="..."}` - Seconds to POI
  - Label values: `eta_type` = "anticipated" or "estimated"

## Dashboard Integration Points

### Overview Dashboard
- Add flight status row at top (y=0-3)
- Existing panels shift down accordingly

### Fullscreen Overview Dashboard
- Add flight status row in top-right corner
- Maintain kiosk mode optimizations

### Network Metrics Dashboard
- Add ETA comparison below network graphs
- Helps correlate network quality with ETA accuracy

### POI Management Dashboard
- Add ETA comparison for POI-specific tracking
- Shows which POIs have estimated vs anticipated times

## Testing Strategy

1. **Panel Rendering:**
   - Verify all panels render without errors
   - Check color coding matches design
   - Verify value mappings work correctly

2. **Data Display:**
   - Confirm Prometheus queries return data
   - Validate label extraction and display
   - Check timestamp formatting

3. **State Transitions:**
   - Verify flight phase changes update panel display
   - Confirm ETA mode follows phase transitions
   - Test manual phase transitions via API

4. **Performance:**
   - Monitor dashboard load time
   - Check memory usage with dual-query panels
   - Verify refresh interval appropriateness (1s)

## Known Limitations

1. **Timeline Panel:**
   - Current Grafana stat panels have limited customization for timeline display
   - May use text panel with markdown rendering as alternative
   - Future: Consider custom plugin for better visualization

2. **Color-Coding:**
   - Colors fixed to anticipated=blue, estimated=green
   - Cannot be dynamically adjusted without dashboard edit

3. **ETA Accuracy Metrics:**
   - No built-in panel for comparing estimated vs actual ETAs
   - Future phase could add variance metrics

## References

- **Metrics Definition:** `backend/starlink-location/app/core/metrics.py` (Phase 5)
- **API Endpoints:** `backend/starlink-location/app/api/flight_status.py` (Phase 4)
- **Existing Dashboards:** `monitoring/grafana/provisioning/dashboards/*.json`
- **Dashboard Skill Guide:** `.claude/skills/grafana-dashboard/`

## Success Criteria

- ✅ All 4 panel types created and tested
- ✅ Flight phase indicator shows correct values (0/1/2)
- ✅ ETA mode indicator shows correct values (0/1)
- ✅ Color-coded ETAs appear in network and POI dashboards
- ✅ Panels integrated into 4 dashboards without overlap
- ✅ Prometheus queries validate successfully
- ✅ All panels visible and functional in Grafana UI
- ✅ No dashboard layout conflicts or overlapping panels
