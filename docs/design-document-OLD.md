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

### High-Level Overview

```text
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
│   starlink-location (Python/FastAPI)       │
│  ├── API Layer (routes, pois, missions)    │
│  ├── Services (managers, calculators)      │
│  ├── Core (metrics, config, models)        │
│  ├── Simulation or Live Polling            │
│  └── /metrics (Prometheus endpoint)        │
└──────────────┬─────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │ Starlink Dish (Live)│
    │ or Simulator Engine │
    └─────────────────────┘
```

### Backend Service Architecture (Post-Refactoring)

The `starlink-location` service is organized into focused modules:

```text
app/
├── api/                        # FastAPI routes (3 modules + 14 sub-modules)
│   ├── __init__.py            # Endpoint router registration
│   ├── geojson.py             # GeoJSON conversion
│   ├── routes/                # Route management (290 lines)
│   │   ├── __init__.py
│   │   ├── management.py      # list_routes, get_route, status
│   │   ├── upload.py          # upload_route (305 lines)
│   │   ├── activation.py      # activate, deactivate routes
│   │   ├── download.py        # download KML files
│   │   ├── eta/               # ETA calculations
│   │   │   ├── waypoint.py    # ETA to specific waypoints
│   │   │   └── location.py    # ETA to arbitrary locations
│   │   ├── timing/            # Route timing profile endpoints
│   │   │   ├── profile.py     # Get timing data
│   │   │   └── progress.py    # Route progress tracking
│   │   └── live_mode.py       # Live position updates
│   ├── pois/                  # POI management (5 modules)
│   │   ├── __init__.py
│   │   ├── crud.py            # POI CRUD operations (388 lines)
│   │   ├── etas.py            # POI ETAs with dual-mode logic (429 lines)
│   │   ├── stats.py           # POI statistics (316 lines)
│   │   └── helpers.py         # Helper functions
│   └── missions/              # Mission management (5 modules)
│       ├── __init__.py
│       ├── activation.py      # Mission lifecycle endpoints
│       ├── routes.py          # Mission routes (7 modules in v0.3)
│       ├── export/            # Export functionality (8 modules)
│       │   ├── __main__.py    # Export orchestration (2,126 lines)
│       │   ├── map_generator.py
│       │   ├── chart_generator.py
│       │   ├── csv_exporter.py
│       │   ├── xlsx_exporter.py
│       │   ├── pdf_exporter.py
│       │   ├── pptx_exporter.py
│       │   └── data_transform.py
│       └── package/           # Package operations (4 modules)
│           └── __main__.py    # Mission packaging
│
├── services/                  # Business logic layer (5 modules)
│   ├── __init__.py
│   ├── poi_manager.py         # POI lifecycle (274 lines)
│   ├── route_manager.py       # Route lifecycle (321 lines)
│   ├── flight_state_manager.py # Flight phase tracking (298 lines)
│   ├── eta/                   # ETA calculations
│   │   ├── projection.py      # Position projection
│   │   └── calculator.py      # ETA computation
│   └── route_eta/             # Route-aware ETA (8 modules in v0.3)
│       ├── calculator.py      # Main calculation engine
│       └── [timing sub-modules]
│
├── satellites/                # Satellite & coverage (3 modules)
│   ├── coverage.py            # Coverage calculations
│   ├── kmz_importer.py        # KMZ file import (384 lines)
│   └── rules.py               # Satellite rules
│
├── mission/                   # Mission models & processing
│   ├── models.py              # Mission data models
│   ├── storage.py             # Mission persistence (245 lines)
│   ├── routes_v2.py           # Mission route handling (2,079 lines)
│   ├── timeline_builder/      # Timeline generation (8 modules)
│   │   ├── events.py          # Event definitions
│   │   └── [builder sub-modules]
│   ├── exporter/              # Export implementation (8 modules)
│   └── package/               # Package operations (4 modules)
│
├── live/                      # Live mode connection
│   ├── client.py              # Starlink dish gRPC client
│   └── starlink_pb2.py        # Protobuf definitions
│
├── simulation/                # Simulation engine (5 modules)
│   ├── coordinator.py         # Simulation orchestration
│   ├── position.py            # Position simulation (287 lines)
│   ├── route.py               # Route following
│   ├── metrics.py             # Metric generation
│   └── events.py              # Event simulation
│
├── core/                      # Core infrastructure
│   ├── config.py              # Configuration management (119 lines)
│   ├── models.py              # Core data models
│   └── metrics/               # Metrics collection (3 modules)
│       ├── __init__.py
│       ├── prometheus_metrics.py # Prometheus registry
│       └── metric_updater.py  # Metric updates
│
└── models/                    # Domain models (3 modules)
    ├── poi.py                 # POI data model (186 lines)
    ├── route.py               # Route data model (274 lines)
    └── [other models]

Frontend/
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   └── RouteMap/
│   │   │       ├── RouteMap.tsx         (146 lines)
│   │   │       ├── RouteLayer.tsx       (120 lines)
│   │   │       ├── RoutePopup.tsx       (95 lines)
│   │   │       ├── SearchBox.tsx        (87 lines)
│   │   │       └── RouteLegend.tsx      (68 lines)
│   │   └── missions/
│   │       ├── MissionList.tsx          (165 lines)
│   │       ├── MissionCard.tsx          (138 lines)
│   │       ├── CreateMissionDialog.tsx  (142 lines)
│   │       ├── ImportDialog.tsx         (156 lines)
│   │       ├── ExportDialog.tsx         (189 lines)
│   │       └── AddLegDialog.tsx         (127 lines)
│   ├── pages/
│   │   ├── LegDetailPage/
│   │   │   ├── LegDetailPage.tsx        (165 lines)
│   │   │   ├── LegHeader.tsx            (82 lines)
│   │   │   ├── LegChart.tsx             (98 lines)
│   │   │   ├── LegStats.tsx             (91 lines)
│   │   │   └── useLegData.ts            (137 lines) - ⚠️ Critical eslint issues
│   │   └── SatelliteManagerPage/
│   │       ├── SatelliteManagerPage.tsx (77 lines)
│   │       ├── KaOutageConfig.tsx       (156 lines)
│   │       ├── KuOutageConfig.tsx       (127 lines)
│   │       └── XBandConfig.tsx          (118 lines)
│   └── services/
│       ├── missions.ts                  (154 lines)
│       ├── routes.ts                    (189 lines)
│       └── pois.ts                      (112 lines)
```

**Key Architectural Improvements (Phase 3-7):**

- **50+ focused modules** created (avg 200 lines each)
- **Service layer** separates business logic from API endpoints
- **Clear separation of concerns**: api/ → services/ → models/
- **Zero circular dependencies** (verified in Phase 6)
- **Frontend components** all under 300 lines with sub-components for complex UI
- **All TypeScript** at 100% under 300 lines compliance

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

**Language:** Python 3.13 (FastAPI + prometheus_client + Pydantic)

**Architecture:** Modular layered design (50+ focused modules)

#### API Layer (`app/api/`)

- **routes/** - Route management (upload, activate, deactivate, ETA
  calculations)
- **pois/** - POI CRUD, ETAs with dual-mode logic, statistics
- **missions/** - Mission lifecycle, export/import, packaging
- **geojson.py** - KML to GeoJSON conversion for Grafana

#### Services Layer (`app/services/`)

- **poi_manager.py** - POI lifecycle and state management
- **route_manager.py** - Route lifecycle and persistence
- **flight_state_manager.py** - Flight phase tracking (pre_departure, in_flight,
  post_arrival)
- **eta/** - ETA calculations and position projection
- **route_eta/** - Route-aware ETA with timing data (v0.3.0+)

#### Core Infrastructure (`app/core/`)

- **config.py** - Configuration management (STARLINK_MODE, SIMULATION_MODE,
  environment variables)
- **metrics/** - Prometheus metrics registry and updates

#### Domain Models (`app/models/`)

- **poi.py** - POI data structures (274 lines)
- **route.py** - Route data structures (186 lines)
- **mission/** - Mission-related models

#### Operational Modes

- **Live Mode:** Polls Starlink dish via gRPC at
  `STARLINK_DISH_HOST:STARLINK_DISH_PORT`
- **Simulation Mode:** Generates realistic telemetry with optional KML route
  following
- **Hybrid:** Automatic fallback to simulation if dish unavailable

#### Endpoints

- **Core Metrics & Health:**
  - `/metrics` → Prometheus metrics (position, network, flight status)
  - `/health` → Service health with connection status
  - `/docs` → Swagger API documentation

- **Route Management:**
  - `POST /api/routes/upload` - Upload KML routes
  - `GET /api/routes` - List all routes
  - `GET /api/routes/{id}` - Get route details
  - `POST /api/routes/{id}/activate` - Activate a route
  - `POST /api/routes/deactivate` - Stop following route
  - `DELETE /api/routes/{id}` - Delete route
  - `GET /api/routes/{id}/download` - Download original KML
  - `GET /api/routes/{id}/eta/waypoint/{index}` - ETA to waypoint (v0.3.0+)
  - `GET /api/routes/{id}/progress` - Route progress tracking (v0.3.0+)

- **POI Management:**
  - `GET /api/pois` - List POIs with filtering
  - `POST /api/pois` - Create POI
  - `PUT /api/pois/{id}` - Update POI
  - `DELETE /api/pois/{id}` - Delete POI
  - `GET /api/pois/etas` - Get ETAs to all POIs (dual-mode:
    anticipated|estimated)
  - `GET /api/pois/{id}/stats` - POI-specific statistics

- **Mission Management:**
  - `POST /api/missions` - Create mission
  - `GET /api/missions` - List missions
  - `GET /api/missions/{id}` - Get mission details
  - `POST /api/missions/{id}/activate` - Activate mission
  - `POST /api/missions/import` - Import mission package
  - `GET /api/missions/{id}/export` - Export mission as KML/KMZ/XLSX/PDF/PPTX
  - `POST /api/missions/{id}/legs` - Add leg to mission
  - `DELETE /api/missions/{id}` - Delete mission

- **Flight Status & ETA Modes (v0.3.0+):**
  - `GET /api/flight-status` - Current flight phase and ETA mode
  - `POST /api/flight-status/depart` - Manual departure trigger (testing)
  - `POST /api/flight-status/arrive` - Manual arrival trigger (testing)
  - `GET /api/pois/etas` - POI ETAs with `eta_type`, `flight_phase`,
    `is_pre_departure` fields

### ✈️ Flight State Manager & ETA Modes

- **Purpose:** Track global flight phase (`pre_departure`, `in_flight`,
  `post_arrival`) and expose dual ETA strategies:
  - **Anticipated mode:** Uses route timing metadata prior to departure.
  - **Estimated mode:** Blends live speed with planned profile once airborne.
- **Key Endpoints:**
  - `GET /api/flight-status` – consolidated snapshot with phase, ETA mode,
    countdowns, and route context.
  - `POST /api/flight-status/depart` / `/arrive` – manual overrides to force
    phase transitions (used for testing and operations).
  - `GET /api/pois/etas` – returns POI entries with `eta_type`, `flight_phase`,
    and `is_pre_departure` fields.
  - `GET /api/routes` / `/api/routes/{id}` – now include `flight_phase`,
    `eta_mode`, and `has_timing_data`.
- **Prometheus Metrics:**
  - `starlink_flight_phase`, `starlink_eta_mode`,
    `starlink_time_until_departure_seconds`.
  - `starlink_eta_poi_seconds` and `starlink_distance_to_poi_meters` now include
    an `eta_type="anticipated|estimated"` label.
- **Design Notes:**
  - `FlightStateManager` is a singleton with thread-safe updates and automatic
    detection hooks (`check_departure`, `check_arrival`).
  - Metrics exporter seeds a default cruise speed (<0.5 kn fallback) to keep
    pre-departure ETAs non-negative.
  - Route activation resets flight state to `pre_departure`, ensuring
    anticipated mode is the default for new missions.
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

### 🎨 Mission Planner Frontend

**Technology:** TypeScript/React with Vite, Tailwind CSS

**Architecture:** Component-based UI with service layer

#### Components Structure (100% under 300 lines)

**Common Components:**

- **RouteMap/** - Interactive route visualization (5 sub-components)
  - `RouteMap.tsx` (146 lines) - Main container
  - `RouteLayer.tsx` (120 lines) - Map layer rendering
  - `RoutePopup.tsx` (95 lines) - Route information popup
  - `SearchBox.tsx` (87 lines) - Route search functionality
  - `RouteLegend.tsx` (68 lines) - Map legend

**Mission Management:**

- `MissionList.tsx` (165 lines) - List of missions
- `MissionCard.tsx` (138 lines) - Individual mission card
- `CreateMissionDialog.tsx` (142 lines) - Create new mission
- `ImportDialog.tsx` (156 lines) - Import mission package
- `ExportDialog.tsx` (189 lines) - Export mission to various formats
- `AddLegDialog.tsx` (127 lines) - Add leg to mission

**Pages:**

- **LegDetailPage/** - Detailed leg information (5 sub-components)
  - `LegDetailPage.tsx` (165 lines) - Main page
  - `LegHeader.tsx` (82 lines) - Header with leg title
  - `LegChart.tsx` (98 lines) - Timeline/profile chart
  - `LegStats.tsx` (91 lines) - Statistics panel
  - `useLegData.ts` (137 lines) - Data fetching hook ⚠️ Critical ESLint issues
    (setState in useEffect)

- **SatelliteManagerPage/** - Satellite configuration (4 sub-components)
  - `SatelliteManagerPage.tsx` (77 lines) - Main page
  - `KaOutageConfig.tsx` (156 lines) - Ka-band outage configuration
  - `KuOutageConfig.tsx` (127 lines) - Ku-band outage configuration
  - `XBandConfig.tsx` (118 lines) - X-band outage configuration

#### Services Layer

- **missions.ts** (154 lines) - Mission API client
- **routes.ts** (189 lines) - Route API client
- **pois.ts** (112 lines) - POI API client

#### Styling

- Tailwind CSS configuration with custom design system
- Dark mode support via Tailwind
- Responsive grid layouts

#### Known Issues

- **useLegData.ts:** Critical ESLint violations in useEffect hook (setState
  patterns need refactoring)
- **routes.ts:** 11 `any` types remain (TypeScript strict mode compliance
  needed)

### 🗺️ Grafana

- Visualizes data from Prometheus
- Panels:
  - Time-series for latency, throughput, obstructions
  - Real-time map (using **Geomap** plugin with route overlays)
  - POI + ETA table with dual-mode indicators
  - Flight status and phase indicators
  - Route progress tracking
- Supports overlay layers (route.geojson from `/api/geojson`, weather radar
  tiles)
- Dashboards:
  - **Fullscreen Overview** - Complete system status with map, metrics, ETAs
  - **Flight Timeline** - Mission timeline and phase tracking
  - **Route Analysis** - Route-specific metrics and progress

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

```text
<https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=APIKEY>
```

### Routes & POIs

- User mounts `/data/routes/` directory with `.kml` files.
- On startup, system auto-converts to `/route.geojson`.
- Grafana loads via URL layer in the Geomap panel.
- Routes support embedded timing metadata for realistic simulation and ETA
  calculations.

### ETA Calculations

#### Standard ETA (All Routes)

- Based on current speed & great-circle distance (Haversine formula)
- Published as Prometheus metrics:

```text
starlink_eta_poi_seconds{name="WaypointA"}  450
starlink_distance_to_poi_meters{name="WaypointA"}  23000
```

#### Timing-Aware ETA (Routes with Timing Data)

**New in Version 0.3.0:** Full ETA route timing system

- **Automatic Timing Extraction:** Parses
  `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ` from KML descriptions
- **Speed Calculations:** Computes segment speeds using haversine distance and
  timing data
- **Route-Aware ETA:** Calculates ETAs along the KML path using expected segment
  speeds
- **Timing Profile:** Aggregates route-level timing metrics (departure, arrival,
  duration)
- **Published Metrics:**

```text
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

- **Performance:** ETA cache with 5-second TTL, accuracy tracking, historical
  metrics

---

## 6. Development Workflow

1. **Clone repo & build stack**

   ```bash
   docker compose up -d
   ```

1. **Enable simulation**

   ```bash
   export SIMULATION_MODE=true
   ```

1. **Access Grafana** [http://localhost:3000](http://localhost:3000)

1. **Load the dashboard**
   - Observe live-moving simulated position
   - Adjust KML route or weather layer as desired
   - Test control buttons and metrics refresh

1. **Switch to Live Mode**

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
with expected waypoint arrival times. Enables realistic simulation of timed
routes, accurate ETA calculations, and comprehensive performance monitoring.

**Capabilities:**

- Automatic extraction of timing metadata from KML files
- Real-time ETA calculations to waypoints and arbitrary locations
- Route timing profile visualization in Grafana
- Simulator respects timing data for authentic movement
- Cache-backed performance optimization (5-second TTL)
- Historical ETA accuracy tracking
- Live mode integration for Starlink terminal position feeds

**Testing:** 451 tests passing (100% coverage)
