# KML Route Import - Implementation Context

**Last Updated:** 2025-11-02 - Phase 4 Complete, POI Filtering Feature Complete

**Feature Branch:** `feature/kml-route-import`

---

## Overview

This document provides quick-reference context for implementing the KML route import and management feature. It consolidates key file locations, existing implementations, and technical decisions.

---

## Current Implementation Status

- **Phase 1 (Backend API)** ✅ Complete — upload/list/detail/activation/deletion endpoints live and integrated with `RouteManager`.
- **Phase 2 (Route UI)** ✅ Complete — web UI at `/ui/routes` supports upload, activation, download, delete, and detail modals.
- **Phase 3 (Grafana Visualization)** ✅ Complete — dashboard displays the active route via `/api/route/coordinates`, with deactivate controls in UI.
- **Phase 4 (Route-POI Integration)** ✅ Complete — route uploads can auto-import waypoint placemarks as POIs, API responses include import metrics, and UI surfaces route-scoped POIs with filters.
- **POI Category Filtering** ✅ Complete — Grafana dashboard variable for filtering POIs by category (departure, arrival, waypoint, alternate). Backend API supports category parameter. Dashboard filters applied to both map and table panels.

---

## Highlights From Session 5 (2025-11-02)

- **Route Upload Enhancements:** `POST /api/routes/upload` now accepts `import_pois`, converts waypoint placemarks into persisted POIs via `_import_waypoints_as_pois`, and echoes created/skipped counts in the response (`RouteResponse.imported_poi_count`).
- **POI Filtering Hardening:** `POIManager.list_pois()` and `count_pois()` now return route-specific entries exclusively, enabling `/api/pois` and `/api/route.geojson` to show only active-route POIs by default.
- **UI Integration:** `/ui/routes` exposes an “Import POIs” checkbox, reports POI counts in the details modal and delete confirmation, and `/ui/pois` adds route selection/filtering with badges distinguishing global vs. route-scoped POIs.
- **Regression Coverage:** Added waypoint regression in `backend/starlink-location/tests/unit/test_kml_parser.py`, adjusted POI manager expectations, and introduced an API-level integration test that verifies `import_pois=true` creates the expected POIs.

---

## Files Modified This Session

- `backend/starlink-location/app/api/routes.py` — imports waypoint metadata into POIs on upload and surfaces counts in responses.
- `backend/starlink-location/app/api/ui.py` — adds import toggle, route-aware delete messaging, POI route selector, and filtering controls.
- `backend/starlink-location/app/models/route.py` — extends `RouteResponse`/`RouteDetailResponse` with POI metrics and waypoint payloads.
- `backend/starlink-location/app/services/poi_manager.py` — restricts filtered queries to route-specific POIs.
- `backend/starlink-location/tests/*` — unit/integration coverage for waypoint parsing and POI import behaviour.
- `dev/STATUS.md`, `SESSION-NOTES.md`, and task checklist — recorded Phase 4 completion and queued Phase 5.

---

## Pending / Next Steps

1. Phase 5 kickoff: wire `RouteManager` into the simulation follower so the active route drives telemetry playback.
2. Emit route-progress metrics (e.g., `% complete`, current waypoint) for Prometheus once simulation integration is live.
3. Backfill automated KML edge-case fixtures (alternates, disjoint legs) to harden the parser before Phase 6 testing.
4. Expand UI validation/error messaging for bulk POI imports and ensure accessibility of the new route filters.
5. Address environment gaps (install `pytest`) ahead of the broader regression pass in Phase 6.

---

---

## Key Files and Locations

### Backend Files

#### Route Infrastructure (Already Implemented)
```
backend/starlink-location/app/
├── models/
│   └── route.py                    # RoutePoint, RouteMetadata, ParsedRoute, RouteResponse
├── services/
│   ├── kml_parser.py               # parse_kml_file(), validate_kml_file(), KMLParseError
│   └── route_manager.py            # RouteManager class with file watching
├── api/
│   ├── geojson.py                  # /api/route.geojson, /api/route.json (already working)
│   └── ui.py                       # UI serving endpoints (extend for /ui/routes)
└── simulation/
    ├── kml_follower.py             # Route following in simulation mode
    └── coordinator.py              # SimulationCoordinator (needs route integration)
```

#### Files Created (Phase 1)
```
backend/starlink-location/app/
├── api/
│   └── routes.py                   # ✅ CREATED: Route CRUD API endpoints (380 lines)
```

#### Files to Create (Phase 2+)
```
backend/starlink-location/app/
└── templates/
    └── routes.html                 # TODO: Route management UI template
```

### Frontend Files

#### Grafana Dashboard
```
monitoring/grafana/provisioning/dashboards/
└── fullscreen-overview.json        # MODIFY: Add active route layer
```

### Data Directories
```
/data/
├── routes/                         # KML files watched by RouteManager
├── pois.json                       # POI storage (route_id field links to routes)
└── sample_routes/                  # NEW: Example KML files for testing
```

---

## Existing Implementation Details

### Route Manager (`app/services/route_manager.py`)

**Key Methods:**
```python
class RouteManager:
    def __init__(self, routes_dir="/data/routes"):
        # Initializes file watcher, in-memory cache

    def start_watching(self):
        # Starts watchdog Observer for KML files

    def list_routes(self) -> dict[str, dict]:
        # Returns: {route_id: {id, name, description, point_count, is_active, imported_at}}

    def get_route(self, route_id: str) -> Optional[ParsedRoute]:
        # Returns full route with points

    def get_active_route(self) -> Optional[ParsedRoute]:
        # Returns currently active route

    def activate_route(self, route_id: str) -> bool:
        # Sets active route (only one at a time)

    def deactivate_route(self):
        # Clears active route

    def get_route_errors(self) -> dict[str, str]:
        # Returns parse errors by route_id
```

**Current Behavior:**
- Automatically loads KML files from `/data/routes/` on startup
- Watches for new/modified/deleted KML files
- Maintains in-memory cache of parsed routes
- Tracks one active route at a time
- route_id = filename without .kml extension

**Location in Code:**
- Instantiated in: `backend/starlink-location/app/api/geojson.py:16`
- Used by: geojson.py for serving route data
- Not yet integrated with main.py startup

### KML Parser (`app/services/kml_parser.py`)

**Key Function:**
```python
def parse_kml_file(file_path: str | Path) -> Optional[ParsedRoute]:
    """
    Parse KML file and extract:
    - Route name (from kml:name element)
    - Route description (from kml:description)
    - LineString coordinates
    - Returns ParsedRoute with metadata and points
    """
```

**Current Features (as of Session 4):**
- Parses all placemarks, building data classes for geometry, inline styles, and document order.
- Identifies the primary departure/arrival waypoints (using route name patterns or first/last fallback).
- Chains connected route segments to form a single primary coordinate list; falls back to concatenation if heuristics fail.
- Returns:
  - `ParsedRoute.points`: filtered sequence of `RoutePoint` objects for the primary path.
  - `ParsedRoute.waypoints`: structured `RouteWaypoint` objects with roles and styling hints for POI creation.
- Raises `KMLParseError` with informative messages when no coordinate data is found or the file cannot be parsed.

**Current Limitations:**
- Waypoint roles are heuristic (style-based) and may need refinement once more samples arrive.
- Automated regression tests for complex KML inputs still pending.
- POI auto-import pipeline not yet wired into upload flow.

### Parsed Route Model (`app/models/route.py`)

**Structure:**
```python
class RoutePoint(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float]
    sequence: int  # 0-indexed position in route

class RouteMetadata(BaseModel):
    name: str
    description: Optional[str]
    file_path: str
    imported_at: datetime
    point_count: int

class ParsedRoute(BaseModel):
    metadata: RouteMetadata
    points: list[RoutePoint]
    waypoints: list[RouteWaypoint]

    def get_total_distance(self) -> float:
        # Haversine calculation of total route distance

    def get_bounds(self) -> dict:
        # Returns {min_lat, max_lat, min_lon, max_lon}
```

### Existing GeoJSON API (`app/api/geojson.py`)

**Endpoint: GET /api/route.geojson**
- Query params: `include_pois`, `include_position`, `route_id`
- Returns GeoJSON FeatureCollection with:
  - Route as LineString feature
  - Optional POIs as Point features
  - Optional current position

**Current Issues / Follow-ups:**
- route_manager is instantiated locally in geojson.py (should ensure single instance via startup wiring).
- GeoJSON endpoint still delivers legacy LineString data; Grafana layer now prefers `/api/route/coordinates`.
- Need to expose waypoint metadata through dedicated POI/API endpoints once importer is complete.

**Endpoint: GET /api/route.json**
- Returns route metadata without coordinates
- Includes: name, description, point_count, bounds, distance
- Currently returns error if no active route

---

## Technical Decisions

### File Naming Convention
- **Route IDs:** Derived from KML filename without extension
- Example: `nyc-to-boston.kml` → route_id = `nyc-to-boston`
- Handles duplicates: If file exists, append `-1`, `-2`, etc.

### Active Route Concept
- **Only one route active at a time**
- Setting new active route automatically deactivates previous
- Simulation follows active route if set
- POIs filtered to show only those associated with active route

### File Upload Approach
- Use FastAPI's `UploadFile` for file uploads
- Validate file extension before processing
- Save to `/data/routes/` directory
- Let watchdog detect and trigger parse
- Alternative: Parse immediately and only save if valid

### Route Deletion Behavior
- Deleting route also deletes associated POIs (cascade)
- Show warning in confirmation dialog: "This will also delete X associated POIs"
- Use `poi_manager.delete_route_pois(route_id)` from POI manager

### Route Color Scheme
- **Position History:** Blue (#0099ff) - where we've been
- **Active Route:** Orange/Red (#ff6600) - planned path
- **Current Position:** Green - where we are now
- Ensures visual distinction on map

---

## Integration Points

### Route Manager Integration with Main App

**Current State:**
- route_manager instantiated in geojson.py only
- Not started in main.py startup sequence

**Required Changes:**
```python
# In backend/starlink-location/main.py

from app.services.route_manager import RouteManager

# Global instance
_route_manager: RouteManager = None

async def startup_event():
    global _route_manager

    # Initialize route manager
    logger.info_json("Initializing Route Manager")
    _route_manager = RouteManager()
    _route_manager.start_watching()
    logger.info_json(f"Route Manager initialized, watching /data/routes/")

    # Register with API modules
    routes.set_route_manager(_route_manager)  # New routes API
    geojson.set_route_manager(_route_manager)  # Existing GeoJSON API
```

### POI-Route Integration

**Existing POI Fields:**
```python
class POI(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    icon: str
    category: Optional[str]
    description: Optional[str]
    route_id: Optional[str]  # ← Links POI to route
    created_at: datetime
    updated_at: datetime
```

**POI Filtering:**
- `GET /api/pois?route_id=xyz` - Already supported
- Used to show only POIs for active route
- Global POIs have `route_id = None`

**POI Cascade Delete:**
```python
# In POI manager (already implemented):
def delete_route_pois(self, route_id: str) -> int:
    """Delete all POIs associated with a route."""
    # Already implemented in app/services/poi_manager.py:274
```

### Simulation Integration

**Current Simulation Behavior:**
- Uses circular pattern or `/data/sim_routes/` if files exist
- No integration with route manager yet

**Required Integration:**
```python
# In app/simulation/coordinator.py

def __init__(self, config):
    # ... existing code ...

    # Check for active route
    from app.services.route_manager import route_manager
    active_route = route_manager.get_active_route()

    if active_route:
        # Use KMLFollower with active route
        self.follower = KMLFollower(active_route)
    else:
        # Fall back to circular pattern
        self.follower = CircularPattern()
```

---

## API Design Patterns

### Following POI API Pattern

The route API should follow the same pattern as POI API for consistency:

**POI Pattern:**
```python
# List all
GET /api/pois → POIListResponse

# Get one
GET /api/pois/{id} → POIResponse

# Create
POST /api/pois → POIResponse (201)

# Update
PUT /api/pois/{id} → POIResponse

# Delete
DELETE /api/pois/{id} → 204 No Content

# Special endpoints
GET /api/pois/count/total → {"count": N}
GET /api/pois/etas → POIETAListResponse
```

**Route Pattern (to implement):**
```python
# List all
GET /api/routes → RouteListResponse

# Get one
GET /api/routes/{id} → RouteDetailResponse

# Upload (create)
POST /api/routes/upload → RouteResponse (201)

# Delete
DELETE /api/routes/{id} → 204 No Content

# Special endpoints
GET /api/routes/{id}/stats → RouteStatsResponse
POST /api/routes/{id}/activate → {"success": True}
POST /api/routes/deactivate → {"success": True}
GET /api/routes/{id}/download → KML file download
```

---

## Grafana Dashboard Modification

### Current Geomap Configuration

**Panel Location:** Row 0, Grid position (0,2), Size 16w x 22h

**Existing Layers:**
1. **Route History** (blue line showing position history)
   - Uses time series data from Prometheus
   - 1-second sampling interval
   - Query: `starlink_dish_latitude_degrees` and `starlink_dish_longitude_degrees`

2. **Current Position** (green plane marker)
   - Single point with current position
   - Rotation based on heading

**New Layer to Add:**

```json
{
  "name": "Active Route",
  "type": "route",
  "config": {
    "src": "infinity",
    "query": "http://starlink-location:8000/api/route.geojson?include_pois=false",
    "refresh": "5s",
    "color": {
      "fixed": "#ff6600"
    },
    "lineWidth": 3,
    "opacity": 0.7
  },
  "tooltip": {
    "mode": "multi",
    "fields": ["name", "distance_km", "point_count"]
  }
}
```

**Layer Order (bottom to top):**
1. Basemap (OSM)
2. Active Route (underneath)
3. Route History
4. POI Markers
5. Current Position (top)

---

## Testing Strategy

### Unit Tests

**Files to test:**
```
tests/unit/
├── test_kml_parser.py         # Already exists
├── test_route_manager.py      # Already exists
├── test_route_api.py          # NEW: Test route API endpoints
└── test_route_models.py       # NEW: Test route response models
```

**Test Cases:**
- Valid KML upload
- Invalid KML upload (malformed XML)
- Duplicate filename handling
- Route activation/deactivation
- Route deletion with POIs
- Route download

### Integration Tests

**Files to test:**
```
tests/integration/
├── test_route_upload_flow.py      # NEW: End-to-end upload test
├── test_route_geojson.py          # NEW: GeoJSON generation
└── test_route_poi_integration.py  # NEW: Route-POI linking
```

**Test Flows:**
1. Upload → Activate → GeoJSON → Delete
2. Upload with POIs → Delete (verify cascade)
3. Multiple uploads → Switch active route
4. Invalid upload → Error handling

### Manual Testing

**Test Scenarios:**
1. Upload various KML files:
   - Small route (10 points)
   - Large route (1000+ points)
   - Route with embedded POIs
   - Invalid/malformed KML
2. Test UI in different browsers:
   - Chrome, Firefox, Safari
   - Mobile responsive design
3. Test Grafana visualization:
   - Route displays correctly
   - Colors distinct from position history
   - Tooltip shows route info

---

## Sample KML Files

### Simple Route Example
```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>NYC to Boston</name>
    <description>Simple route from New York to Boston</description>
    <Placemark>
      <LineString>
        <coordinates>
          -74.0060,40.7128,0
          -71.0589,42.3601,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
```

### Route with POIs Example
```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Coastal Route</name>
    <Placemark>
      <name>Start Point</name>
      <Point>
        <coordinates>-74.0060,40.7128,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <LineString>
        <coordinates>
          -74.0060,40.7128,0
          -73.5000,41.0000,0
          -72.0000,41.5000,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
```

---

## Dependencies

### Python Packages (Already Installed)
```
fastapi>=0.104.1
pydantic>=2.4.2
watchdog>=3.0.0        # For file watching
python-multipart       # For file uploads (verify installed)
```

### Grafana Plugins
```
- Infinity Data Source  # For fetching JSON/GeoJSON from API
```

---

## Configuration

### Environment Variables

No new environment variables needed. Existing config sufficient:

```bash
# .env
STARLINK_MODE=simulation
```

### Config File

May want to add route-specific settings to `backend/starlink-location/config.yaml`:

```yaml
route:
  max_upload_size_mb: 10
  auto_activate_on_upload: false
  completion_behavior: "loop"  # "loop", "stop", or "reverse"
```

---

## Error Handling

### Upload Errors
- File too large → 413 Request Entity Too Large
- Invalid file type → 400 Bad Request
- Malformed KML → 400 Bad Request with parse error details
- Duplicate filename → Auto-rename or 409 Conflict

### Route Operations
- Route not found → 404 Not Found
- Route already active → 200 OK (idempotent)
- Delete non-existent route → 404 Not Found
- Parse error → Store in route_manager errors, return in list

---

## Performance Considerations

### File Upload
- Limit file size to 10MB (configurable)
- Stream large files to disk (don't load into memory)
- Validate file type before parsing

### KML Parsing
- Large routes (10k+ points) may take >1s to parse
- Consider async parsing for large files
- Cache parsed routes in route manager

### Grafana Display
- Very large routes may slow map rendering
- Consider downsampling for display (keep full data for calculations)
- Limit refresh rate to 5s (routes change infrequently)

---

## Security Considerations

### File Upload
- Validate file extension (.kml only)
- Scan for XML vulnerabilities (XXE attacks)
- Limit file size
- Sanitize filenames (remove path traversal characters)

### File Access
- Only serve files from `/data/routes/` directory
- Prevent directory traversal in route_id
- Use safe path joining (Path() objects, not string concat)

---

## Rollback Plan

If issues arise after deployment:

1. **Revert API changes:**
   - Comment out routes API router registration in main.py
   - Revert to using existing geojson endpoints only

2. **Disable route layer in Grafana:**
   - Remove active route layer from dashboard JSON
   - Fall back to position history only

3. **File safety:**
   - Routes stored in `/data/routes/` are not touched by rollback
   - Can re-enable feature later without data loss

---

## Next Steps

1. ✅ Create planning documents (this file)
2. ⬜ Begin Phase 1: Backend Route Upload API
3. ⬜ Create `app/api/routes.py` with upload endpoint
4. ⬜ Test upload with sample KML files
5. ⬜ Continue through phases sequentially

---

**Document Status:** ✅ Complete and Ready for Implementation

**Last Updated:** 2025-10-31
