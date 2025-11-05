# Design Document: Mobile Starlink Terminal Monitoring Webapp (with Simulation Mode)

## 1. Overview and Objectives

This project aims to build a **Docker-based web application** that monitors and
visualizes real-time metrics from a **mobile Starlink terminal**.  
Since a live terminal isn’t always available, the system will include a **full
simulation mode** for development, testing, and demo purposes.

The end product will:

- Collect or simulate real-time Starlink stats (latency, throughput,
  obstructions, uptime, etc.)
- Plot the terminal’s **position and trajectory** on a live map
- Support **KML route overlays**, POIs, and ETA calculations
- Store all data for historical analysis
- Run as a **self-contained Docker Compose stack**
- Provide a **web dashboard** (Grafana-based) for visualization and control

---

## 2. System Architecture

```
┌────────────────────────────────────────────┐
│                  Grafana                   │
│  ├── Starlink Stats Dashboard              │
│  ├── Map (Geomap / TrackMap)               │
│  ├── POI + ETA Panels                      │
│  └── (Optional) Control Buttons            │
└──────────────┬─────────────────────────────┘
               │ Prometheus Queries
┌──────────────┴─────────────────────────────┐
│               Prometheus                   │
│  ├── Scrapes live/simulated metrics        │
│  └── Stores all time-series data           │
└──────────────┬─────────────────────────────┘
               │ HTTP Metrics / API
┌──────────────┴─────────────────────────────┐
│      starlink-location (Python)            │
│  ├── Simulation or Live Polling            │
│  ├── ETA + Speed Calculation               │
│  ├── /metrics (Prometheus endpoint)        │
│  ├── /api/dish/reboot /stow (control)      │
│  └── /route.geojson (KML-to-GeoJSON)       │
└──────────────┬─────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │ Starlink Dish (Live)│
    │ or Simulator Engine │
    └─────────────────────┘
```

---

## 3. Simulation Mode

### Purpose

Enable full system operation without physical access to a Starlink terminal —
ideal for development and demos.

### Activation

The mode is toggled by an environment variable:

```bash
SIMULATION_MODE=true
```

When `true`, the `starlink-location` service bypasses all gRPC calls and instead
uses a **simulation engine** that generates realistic telemetry and GPS
movement.

### Behavior

| Metric Type           | Simulation Logic                                                    |
| --------------------- | ------------------------------------------------------------------- |
| Latitude/Longitude    | Moves along a generated or imported route (KML or circular pattern) |
| Altitude              | Oscillates slightly (±100 ft) to simulate turbulence                |
| Speed                 | Randomized 150–250 knots (smooth noise)                             |
| Heading               | Derived from trajectory                                             |
| Latency               | Sinusoidal between 40–120 ms                                        |
| Throughput            | Randomized bursts (100–200 Mbps down, 15–30 Mbps up)                |
| Obstructions / Errors | Injected intermittently (1–5% probability)                          |
| Outages               | Occasional brief 2–5s drops                                         |
| Thermal Flags         | Rare random events                                                  |

The simulator produces Prometheus metrics indistinguishable from live data,
ensuring Grafana dashboards require **zero modification**.

### Pre-Recorded Routes

If a `.kml` or `.json` route file is found in `/data/sim_routes/`, the simulator
follows that route sequentially.  
Otherwise, it defaults to a looping circular trajectory.

### Optional API Controls

```bash
POST /api/sim/start
POST /api/sim/stop
POST /api/sim/reset
POST /api/sim/set_route?file=route1.kml
```

---

## 4. Core Components

### 🛰️ `starlink-location` Service

- **Language:** Python (FastAPI + prometheus_client)
- **Modes:**
  - _Live Mode:_ Polls dish via gRPC (using `starlink-client`)
  - _Sim Mode:_ Uses simulated telemetry generator
- **Endpoints:**
  - `/metrics` → Prometheus metrics (lat, lon, speed, latency, etc.)
  - `/api/dish/reboot`, `/api/dish/stow`
  - `/api/sim/*` (simulation controls)

### ✈️ Flight State Manager & ETA Modes

- **Purpose:** Track global flight phase (`pre_departure`, `in_flight`, `post_arrival`) and expose dual ETA strategies:
  - **Anticipated mode:** Uses route timing metadata prior to departure.
  - **Estimated mode:** Blends live speed with planned profile once airborne.
- **Key Endpoints:**
  - `GET /api/flight-status` – consolidated snapshot with phase, ETA mode, countdowns, and route context.
  - `POST /api/flight-status/depart` / `/arrive` – manual overrides to force phase transitions (used for testing and operations).
  - `GET /api/pois/etas` – returns POI entries with `eta_type`, `flight_phase`, and `is_pre_departure` fields.
  - `GET /api/routes` / `/api/routes/{id}` – now include `flight_phase`, `eta_mode`, and `has_timing_data`.
- **Prometheus Metrics:**
  - `starlink_flight_phase`, `starlink_eta_mode`, `starlink_time_until_departure_seconds`.
  - `starlink_eta_poi_seconds` and `starlink_distance_to_poi_meters` now include an `eta_type="anticipated|estimated"` label.
- **Design Notes:**
  - `FlightStateManager` is a singleton with thread-safe updates and automatic detection hooks (`check_departure`, `check_arrival`).
  - Metrics exporter seeds a default cruise speed (<0.5 kn fallback) to keep pre-departure ETAs non-negative.
  - Route activation resets flight state to `pre_departure`, ensuring anticipated mode is the default for new missions.
  - `/route.geojson` (converted from uploaded KML)
- **Features:**
  - ETA + distance calculation to POIs
  - KML → GeoJSON converter (for Grafana overlay)
  - Periodic background updates every 2–5s

### 📈 Prometheus

- Collects metrics from:
  - `starlink-location`
  - (Optionally) `speedtest-exporter`, `blackbox-exporter`
- Retains time-series data (15–30 days by default)
- Supports alert rules (future addition)

### 🗺️ Grafana

- Visualizes data from Prometheus
- Panels:
  - Time-series for latency, throughput, obstructions
  - Real-time map (using **Geomap** or **TrackMap** plugin)
  - POI + ETA table
  - Optional control iframe or plugin buttons
- Supports overlay layers (route.geojson, weather radar tiles)

### ⚙️ Docker Compose Stack

Services:

```yaml
services:
  prometheus:
  grafana:
  starlink-location:
  # optional:
  # starlink-exporter:
  # speedtest-exporter:
```

Default configuration runs in simulation mode for dev and demo use.

---

## 5. Mapping & Routing

### Base Maps

- **OpenStreetMap** (default)
- Optional weather overlay via tile layer:

  ```
  https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=APIKEY
  ```

### Routes & POIs

- User mounts `/data/routes/` directory with `.kml` files.
- On startup, system auto-converts to `/route.geojson`.
- Grafana loads via URL layer in the Geomap panel.
- Routes support embedded timing metadata for realistic simulation and ETA calculations.

### ETA Calculations

#### Standard ETA (All Routes)

- Based on current speed & great-circle distance (Haversine formula)
- Published as Prometheus metrics:

  ```
  starlink_eta_poi_seconds{name="WaypointA"}  450
  starlink_distance_to_poi_meters{name="WaypointA"}  23000
  ```

#### Timing-Aware ETA (Routes with Timing Data)

**New in Version 0.3.0:** Full ETA route timing system

- **Automatic Timing Extraction:** Parses `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ` from KML descriptions
- **Speed Calculations:** Computes segment speeds using haversine distance and timing data
- **Route-Aware ETA:** Calculates ETAs along the KML path using expected segment speeds
- **Timing Profile:** Aggregates route-level timing metrics (departure, arrival, duration)
- **Published Metrics:**

  ```
  starlink_route_timing_has_data{route_id="route-001"} 1
  starlink_route_timing_departure_unix{route_id="route-001"} 1728594300
  starlink_route_timing_arrival_unix{route_id="route-001"} 1728601200
  starlink_eta_to_waypoint_seconds{waypoint="15"} 1800
  starlink_distance_to_waypoint_meters{waypoint="15"} 75000
  starlink_segment_speed_knots{segment="5-6"} 150.0
  ```

- **API Endpoints:**
  - `GET /api/routes/{route_id}/eta/waypoint/{index}` - ETA to specific waypoint
  - `GET /api/routes/{route_id}/eta/location` - ETA to arbitrary location
  - `GET /api/routes/{route_id}/progress` - Route progress and timing
  - `GET /api/routes/active/timing` - Active route timing profile
  - `POST /api/routes/live-mode/active-route-eta` - Live position updates

- **Performance:** ETA cache with 5-second TTL, accuracy tracking, historical metrics

---

## 6. Development Workflow

1. **Clone repo & build stack**

   ```bash
   docker compose up -d
   ```

2. **Enable simulation**

   ```bash
   export SIMULATION_MODE=true
   ```

3. **Access Grafana** [http://localhost:3000](http://localhost:3000)

4. **Load the dashboard**
   - Observe live-moving simulated position
   - Adjust KML route or weather layer as desired
   - Test control buttons and metrics refresh

5. **Switch to Live Mode**

   ```bash
   export SIMULATION_MODE=false
   ```

   (Requires network access to `192.168.100.1:9200`)

---

## 7. Future Enhancements

- **Replay recorded data** (load past logs into simulator)
- **Multi-terminal support** (multiple dishes on one dashboard)
- **Alerting rules** (connectivity loss, high latency)
- **WebSocket push** for faster map updates
- **PostGIS integration** for complex route queries

---

## 8. Summary

| Mode                     | Description                                                | Data Source                        |
| ------------------------ | ---------------------------------------------------------- | ---------------------------------- |
| **Simulation (default)** | Generates realistic Starlink telemetry for offline testing | Internal generator / KML route     |
| **Live**                 | Polls Starlink terminal via gRPC API                       | Dish at `192.168.100.1:9200`       |
| **Hybrid**               | Uses simulation when dish unreachable                      | Fallback logic in location service |
| **Timing-Aware Sim**     | Follows KML routes with expected speeds                    | KML timing metadata                |

The simulator ensures **feature-complete development and demo capability**
without requiring live hardware — you can build and validate dashboards,
routing, ETAs, and control logic before ever connecting a real dish.

### Version 0.3.0: ETA Route Timing Feature

**New in this release:** Advanced timing-aware system for parsing flight plans
with expected waypoint arrival times. Enables realistic simulation of timed routes,
accurate ETA calculations, and comprehensive performance monitoring.

**Capabilities:**
- Automatic extraction of timing metadata from KML files
- Real-time ETA calculations to waypoints and arbitrary locations
- Route timing profile visualization in Grafana
- Simulator respects timing data for authentic movement
- Cache-backed performance optimization (5-second TTL)
- Historical ETA accuracy tracking
- Live mode integration for Starlink terminal position feeds

**Testing:** 451 tests passing (100% coverage)
