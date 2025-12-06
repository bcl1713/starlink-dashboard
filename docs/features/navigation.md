# Navigation & Timing Features

## Route Management Features

### KML Route Import

Upload and manage flight routes in KML format.

**Capabilities:**

- KML file upload via API
- Automatic waypoint extraction
- Route visualization on map
- Timing metadata parsing
- Multiple route storage
- Route activation/deactivation

**Supported KML Features:**

- LineString (routes)
- Point placemarks (POIs)
- Timing information in waypoints
- Description fields
- Extended data

**APIs:**

- `POST /api/routes/upload` - Upload KML file
- `GET /api/routes` - List all routes
- `GET /api/routes/{id}` - Get route details
- `POST /api/routes/{id}/activate` - Activate route
- `DELETE /api/routes/{id}` - Delete route

**See:** [Route API Documentation](../route-api-endpoints.md)

### Route Visualization

Display active routes on Grafana maps.

**Features:**

- Dark orange route line on map
- Waypoint markers
- POI indicators
- Progress tracking
- Distance remaining
- Current waypoint highlight

**Metrics:**

- `starlink_route_progress_percent` - Overall progress
- `starlink_current_waypoint_index` - Current waypoint
- `starlink_distance_to_waypoint_meters` - Distance remaining

### Route Following (Simulation Mode)

Simulator follows uploaded KML routes with realistic movement.

**Features:**

- Follows route waypoints in order
- Respects timing metadata for speed
- Interpolates between waypoints
- Handles altitude changes
- Loops or stops at end (configurable)

**Configuration:** Automatically enabled when route is activated in simulation
mode

**See:** [Route Timing Guide](../route-timing-guide.md)

---

## Point of Interest (POI) Features

### POI Management

Create, update, and manage points of interest along routes.

**Capabilities:**

- Create POIs with lat/lon coordinates
- Name and describe POIs
- Edit existing POIs
- Delete POIs
- List all POIs with filtering
- POI statistics

**APIs:**

- `POST /api/pois` - Create POI
- `GET /api/pois` - List all POIs
- `GET /api/pois/{id}` - Get POI details
- `PUT /api/pois/{id}` - Update POI
- `DELETE /api/pois/{id}` - Delete POI
- `GET /api/pois/stats` - POI statistics

**See:** [POI API Documentation](../api/endpoints/poi.md)

### Real-Time ETA Calculations

Calculate estimated time of arrival to all POIs.

**Features:**

- Real-time distance calculation
- ETA based on current speed and heading
- ETA mode switching (anticipated vs estimated)
- Multiple POI tracking
- Prometheus metrics export
- Grafana table visualization

**ETA Modes:**

- **Anticipated:** Pre-departure estimates (uses planned route timing)
- **Estimated:** In-flight estimates (uses actual speed)

**Metrics:**

- `starlink_eta_poi_seconds` - Time to POI
- `starlink_distance_to_poi_meters` - Distance to POI
- `starlink_bearing_to_poi_degrees` - Direction to POI

**APIs:**

- `GET /api/pois/etas` - Get all POI ETAs
- `GET /api/pois/{id}/eta` - Get specific POI ETA

**See:** [ETA Endpoints Documentation](../api/endpoints/eta.md)

### POI Visualization

Display POIs on Grafana maps with ETA information.

**Features:**

- POI markers on map
- ETA countdown timers in table
- Distance remaining
- Status indicators (approaching, passed, etc.)
- Color coding by proximity
- Alert rules for approaching POIs

---

## Flight Status & Timing

### Flight Phase Tracking

Track flight phases with automatic transitions.

**Phases:**

- `pre_departure` - Before takeoff
- `in_flight` - Airborne
- `post_arrival` - After landing

**Features:**

- Automatic phase detection (simulation mode)
- Manual phase control (testing endpoints)
- Phase-based ETA mode switching
- Grafana phase indicators
- Prometheus metrics

**APIs:**

- `GET /api/flight-status` - Get current phase
- `POST /api/flight-status/depart` - Trigger departure (testing)
- `POST /api/flight-status/arrive` - Trigger arrival (testing)

**See [Flight Status Guide](../route-timing-guide.md) for details.

### Automatic ETA Mode Switching

ETA calculations adapt based on flight phase.

**Behavior:**

- **Pre-departure:** Uses anticipated mode (planned speeds from KML)
- **In-flight:** Switches to estimated mode (actual GPS speed)
- **Post-arrival:** ETAs frozen or cleared

**Configuration:** Automatic based on flight phase (no manual config needed)

**See:** [Route Timing Guide](../route-timing-guide.md)
