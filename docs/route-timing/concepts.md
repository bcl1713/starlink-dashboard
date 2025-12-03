# Route Timing Concepts

<!-- markdownlint-disable MD013 -->

This guide explains the core concepts behind the route timing feature including
how timing data works, ETA modes, and flight phases.

## How Route Timing Works

### 1. Timing Data Extraction

When you upload a KML file, the parser:

1. **Finds timing markers** in coordinate descriptions
2. **Extracts timestamps** using regex pattern: `Time Over
   Waypoint:\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})Z`
3. **Maps timestamps to waypoints** using haversine distance (within 1000m
   tolerance)
4. **Calculates segment speeds** between consecutive timestamped points
5. **Builds route profile** with departure, arrival, and duration

### 2. Speed Calculation

```text
Speed (knots) = Distance (meters) / Time (seconds) * (3600 / 1852)
```

Example: If a point is 74,600 meters away and takes 600 seconds:

```text
Speed = 74,600 / 600 * (3600 / 1852) = 124.33 / 1.852 = 200 knots
```

### 3. ETA Calculation

For routes with timing data:

```text
ETA = Distance to waypoint (meters) / Speed (knots) * (1852 / 3600)
```

### 4. Simulator Behavior

In simulation mode, the simulator:

1. **Checks if route has timing data** at current waypoint
2. **If yes:** Uses expected speed from timing data (small ±0.5 knot variation)
3. **If no:** Falls back to default realistic speeds (45-75 knots)
4. **Result:** Arrival times match expected times when following timed routes

## ETA Modes: Anticipated vs. Estimated

Dual-mode ETA calculations keep operators informed both before departure and
during live operations. Anticipated mode projects the planned schedule, while
estimated mode reacts to real performance.

### Anticipated Mode (Planned Timeline)

- **Phase:** `FlightPhase.PRE_DEPARTURE`
- **Source:** Planned timestamps and segment speeds from the timing profile
- **Behaviour:** Assumes the aircraft follows the filed plan; standalone POIs
  are labelled `is_pre_departure: true`
- **Surfaces:** `/api/flight-status` (`"eta_mode": "anticipated"`),
  `/api/pois/etas` (`"eta_type": "anticipated"`), Prometheus
  (`eta_type="anticipated"`), Grafana badges (**PLANNED**)

```json
{
  "name": "Gate Push",
  "eta_seconds": 900,
  "eta_type": "anticipated",
  "is_pre_departure": true,
  "flight_phase": "pre_departure"
}
```

### Estimated Mode (Live Performance)

- **Phase:** `FlightPhase.IN_FLIGHT` and `FlightPhase.POST_ARRIVAL`
- **Source:** Blends smoothed live speed (120 s window) with the timing profile;
  falls back to distance/speed when timing is absent
- **Behaviour:** Adjusts ETAs to reflect actual performance or manual
  depart/arrive triggers
- **Surfaces:** `/api/flight-status` (`"eta_mode": "estimated"`),
  `/api/pois/etas` (`"eta_type": "estimated"`), Prometheus
  (`eta_type="estimated"`), Grafana badges (**LIVE**)

### Automatic Switching Rules

| Trigger | Phase | ETA Mode | Notes |
| ------- | ----- | -------- | ----- |
| Speed rises above departure threshold (default 40 kn) | `pre_departure → in_flight` | Estimated | Detected by `FlightStateManager.check_departure`; can be forced via `/api/flight-status/depart` |
| Arrival threshold met (within 100 m for 60 s) or `/api/flight-status/arrive` called | `in_flight → post_arrival` | Estimated | Keeps last-known ETAs until reset |
| `/api/flight-status` reset or route deactivated | `post_arrival → pre_departure` | Anticipated | Clears actual departure/arrival timestamps and resumes planned timeline |

### Timed vs. Untimed Routes

- **Timed routes:** Anticipated mode mirrors the KML plan; estimated mode blends
  live speed with expected segment speeds for smoother updates.
- **Untimed routes:** Both modes fall back to distance-based estimation.
  `has_timing_data` stays `false`, but `eta_mode` still tracks the flight phase.

> Tip: During dashboard validation you can issue `/api/flight-status/depart` and
> `/api/flight-status/arrive` to cycle modes instantly without waiting for
> automatic detection.

## Simulation Mode Behavior

### When Timing Data is Present

The simulator:

1. **Reads expected speeds** from KML timing data
2. **Applies small variations** (±0.5 knots) for realism
3. **Produces predictable movement** matching flight plan
4. **Enables validation:** Actual arrival times can be compared to expected

Example:

```text
Route: KADW-PHNL with timing data
Expected Speed Segment 0-1: 200 knots
Actual Simulated Speed: 199.8 to 200.2 knots (with variation)
Result: Realistic movement following expected speeds
```

### When Timing Data is Absent

The simulator falls back to default behavior:

1. **Default speed range:** 45-75 knots (realistic cruising)
2. **Random variations:** Natural speed fluctuations
3. **Full backward compatibility:** Existing routes work unchanged

## Live Mode Integration

When connected to a real Starlink terminal:

1. **Position updates feed** into the active route
2. **ETA calculations** update in real-time
3. **Timing profile** available if route has timing data
4. **Metrics published** to Prometheus for monitoring

Use the `/api/routes/live-mode/active-route-eta` endpoint to:

- Feed real position data
- Get up-to-date progress metrics
- Track against expected timing

## Grafana Dashboard Visualization

The route timing feature adds four new panels to the Fullscreen Overview
dashboard:

### 1. Route Timing Profile Table

Displays:

- Route ID
- Departure time
- Arrival time
- Expected duration
- Segment count with timing

**Data Source:** `starlink_route_timing_*` metrics

### 2. Route Speed Analysis Chart

Shows:

- Expected segment speeds (from timing data)
- Actual speeds (calculated from position changes)
- Speed deviation from planned

**Data Source:** Prometheus queries on speed metrics

### 3. Route Progress Gauge

Displays:

- Overall route progress (0-100%)
- Color-coded thresholds:
  - 0-25%: Green (just starting)
  - 25-75%: Blue (in progress)
  - 75-100%: Orange (nearing completion)

**Data Source:** `starlink_route_progress_percent`

### 4. Distance to Destination Chart

Shows:

- Remaining distance (km)
- Estimated arrival time countdown
- Distance traveled vs planned

**Data Source:** `starlink_distance_to_waypoint_meters`
