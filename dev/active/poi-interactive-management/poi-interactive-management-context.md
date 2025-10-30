# POI Interactive Management - Context Document

**Last Updated:** 2025-10-30

**Feature Branch:** `feature/poi-interactive-management`

---

## Overview

This document provides essential context for implementing the POI Interactive Management feature. It serves as a quick reference for developers working on this feature, highlighting key files, architectural decisions, dependencies, and integration points.

---

## Key Files and Locations

### Backend Files

#### POI Data Models
- **File:** `backend/starlink-location/app/models/poi.py`
- **Purpose:** POI data models (POI, POICreate, POIUpdate, POIResponse, POIListResponse)
- **Status:** ✅ Complete - No changes needed
- **Notes:** Well-structured Pydantic models with validation and examples

#### POI API Endpoints
- **File:** `backend/starlink-location/app/api/pois.py`
- **Purpose:** REST API endpoints for POI CRUD operations
- **Status:** ✅ Complete - Functional as-is
- **Endpoints:**
  - `GET /api/pois` - List POIs (with optional route filtering)
  - `GET /api/pois/{poi_id}` - Get specific POI
  - `POST /api/pois` - Create POI
  - `PUT /api/pois/{poi_id}` - Update POI
  - `DELETE /api/pois/{poi_id}` - Delete POI
  - `GET /api/pois/count/total` - Count POIs

#### POI Manager Service
- **File:** `backend/starlink-location/app/services/poi_manager.py`
- **Purpose:** POI storage, retrieval, and business logic
- **Status:** ✅ Complete - Manages `/data/pois.json`
- **Features:**
  - In-memory caching for performance
  - Automatic file creation
  - Timestamp tracking
  - Route-specific POI filtering
  - CRUD operations

#### Prometheus Metrics
- **File:** `backend/starlink-location/app/core/metrics.py`
- **Purpose:** Prometheus metric definitions
- **Status:** ⚠️ Needs Enhancement
- **Existing Metrics:**
  - `starlink_eta_poi_seconds{name="..."}` - ETA to POI
  - `starlink_distance_to_poi_meters{name="..."}` - Distance to POI
- **Changes Needed (Phase 1):**
  - Ensure metrics are updated in real-time based on telemetry
  - Add POI metadata to metric labels (category, icon) if possible
  - Create aggregated ETA endpoint: `GET /api/pois/etas`

#### Backend Main Application
- **File:** `backend/starlink-location/app/main.py` (or wherever routes are registered)
- **Purpose:** FastAPI application setup
- **Status:** ⚠️ Check if POI routes are registered
- **Changes Needed (Phase 5):**
  - Add route for POI management UI: `GET /ui/pois`
  - Serve static HTML/JS for POI management interface

### Frontend Files

#### Fullscreen Overview Dashboard
- **File:** `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
- **Purpose:** Main dashboard with map and metrics
- **Status:** ⚠️ Needs Enhancement
- **Current Structure:**
  - **Geomap Panel (ID: 1):**
    - Grid position: (0,2), size: 16w x 22h
    - Layers:
      1. Route History (blue line) - Query E & F
      2. Current Position (green plane) - Query A, B, C, D
    - Basemap: OpenStreetMap
    - Tooltips: Enabled (mode: details)
- **Changes Needed (Phase 2):**
  - Add 3rd layer: POI markers
  - Configure Infinity data source for `/api/pois`
  - Add POI marker styling (icon, color, size)
  - Add POI labels
- **Changes Needed (Phase 3):**
  - Add query for ETA data: `/api/pois/etas`
  - Join ETA data with POI data
  - Configure tooltip content (name, ETA, distance)
  - Add color-coding by ETA (red/orange/yellow/blue)

#### POI Management Dashboard (to be created)
- **File:** `monitoring/grafana/provisioning/dashboards/poi-management.json` (Phase 4, Option B)
- **Purpose:** Dedicated dashboard for POI table view and management
- **Status:** 🔨 To be created
- **Contents:**
  - Table panel with POI list and ETAs
  - Optional: Small map preview
  - Link to fullscreen overview
  - Iframe to POI management UI (Phase 5)

### Configuration Files

#### Docker Compose
- **File:** `docker-compose.yml`
- **Purpose:** Container orchestration
- **Status:** ✅ No changes expected
- **Notes:** Backend already accessible from Grafana container

#### Environment Variables
- **File:** `.env`
- **Purpose:** Application configuration
- **Status:** ✅ No changes expected
- **Relevant Settings:**
  - `STARLINK_MODE=simulation` - Safe for testing POI features

#### Grafana Provisioning
- **Files:**
  - `monitoring/grafana/provisioning/datasources/`
  - `monitoring/grafana/provisioning/dashboards/`
- **Status:** ⚠️ May need Infinity data source config (Phase 2)

### Data Storage

#### POI Data File
- **File:** `/data/pois.json` (Docker volume mount)
- **Purpose:** Persistent POI storage
- **Structure:**
```json
{
  "pois": {
    "poi-id-1": {
      "id": "poi-id-1",
      "name": "JFK Airport",
      "latitude": 40.6413,
      "longitude": -73.7781,
      "icon": "airport",
      "category": "airport",
      "description": "John F. Kennedy International Airport",
      "route_id": null,
      "created_at": "2025-10-30T12:00:00",
      "updated_at": "2025-10-30T12:00:00"
    }
  },
  "routes": {}
}
```
- **Status:** ✅ Auto-created by POIManager if missing

---

## Architectural Decisions

### Decision: Use File-based POI Storage

**Rationale:**
- Already implemented and working
- Sufficient for expected POI counts (< 1000)
- Easy to backup and version control
- Simple for single-user deployments

**Alternatives Considered:**
- PostgreSQL/SQLite: Overkill for current needs
- Redis: No persistence by default
- Cloud storage: Adds complexity

**Trade-offs:**
- ✅ Pros: Simple, portable, version-controllable
- ❌ Cons: No concurrent write handling, limited scalability

**Future Migration Path:**
- If > 1000 POIs or multi-user: Migrate to PostgreSQL
- POIManager abstraction makes this migration straightforward

---

### Decision: Grafana Infinity Plugin for POI Data

**Rationale:**
- Native Grafana integration
- Supports JSON API endpoints directly
- No custom plugin development required
- Flexible data transformations

**Alternatives Considered:**
- Custom Grafana panel plugin: Too much development effort
- Prometheus metrics only: Hard to pass complex data structures
- SimpleJSON plugin: Less feature-rich than Infinity

**Trade-offs:**
- ✅ Pros: Quick setup, powerful transformations
- ❌ Cons: Requires plugin installation (may need Grafana admin access)

**Fallback:**
- If Infinity not available: Use HTTP API data source or SimpleJSON plugin

---

### Decision: Separate POI Management UI

**Rationale:**
- Grafana dashboards optimized for visualization, not data entry
- Custom UI allows better UX (forms, validation, map click-to-place)
- Keeps Grafana dashboard clean and focused
- Backend can serve simple HTML/JS

**Alternatives Considered:**
- Grafana Forms: Limited functionality, version-dependent
- Data Manipulation plugin: Not widely available
- Edit POIs via API only: Poor UX

**Trade-offs:**
- ✅ Pros: Better UX, more control, easier to extend
- ❌ Cons: Additional development effort, iframe integration complexity

**Implementation:**
- Phase 5: Backend serves HTML UI at `/ui/pois`
- Embed in Grafana via iframe panel or dashboard link

---

### Decision: Color-code POI Markers by ETA

**Rationale:**
- Provides at-a-glance situational awareness
- Industry standard (red = immediate, yellow = near-term, blue = distant)
- Helps prioritize attention

**Color Scheme:**
- 🔴 Red: ETA < 5 minutes (imminent)
- 🟠 Orange: ETA 5-15 minutes (approaching)
- 🟡 Yellow: ETA 15-60 minutes (near-term)
- 🔵 Blue: ETA > 60 minutes (distant)

**Alternatives Considered:**
- Single color: Less informative
- Distance-based: Less intuitive than time-based
- Custom user colors: Adds configuration complexity

**Trade-offs:**
- ✅ Pros: Intuitive, actionable information
- ❌ Cons: May be hard to see on some basemaps (mitigation: use stroke/outline)

---

## Dependencies and Integration Points

### Backend Dependencies

**Existing (No Changes Needed):**
- FastAPI (API framework)
- Pydantic (data validation)
- Prometheus client (metrics)

**New (If Implementing Custom UI in Phase 5):**
- Jinja2 (HTML templates) - Optional, can use static HTML
- Leaflet.js (map widget) - For click-to-place POI feature

**Python Packages:**
```bash
# Already in requirements.txt (likely)
fastapi
pydantic
prometheus-client

# May need to add (Phase 5)
jinja2  # If using server-side templates
```

### Frontend Dependencies

**Grafana Plugins Required:**
- **Infinity Data Source Plugin**
  - Purpose: Fetch POI data from backend JSON API
  - Installation: Grafana Admin → Plugins → Search "Infinity" → Install
  - Status: ⚠️ Check if already installed
  - Alternative: SimpleJSON or HTTP API data source

**Grafana Version:**
- Current: 11.1.0 (from fullscreen-overview.json)
- Required: 10.0+ (for Infinity plugin compatibility)
- Status: ✅ Compatible

### Infrastructure Integration

**Docker Networking:**
- Backend container: `starlink-location` (port 8000)
- Grafana container: `grafana` (port 3000)
- Network: Default bridge or custom (check docker-compose.yml)
- **Status:** ✅ Containers can communicate via service names

**Volume Mounts:**
- `/data` volume: Shared between backend and host
- POI file location: `/data/pois.json`
- **Status:** ✅ Volume persists across restarts

**API Accessibility:**
- Backend API accessible at: `http://starlink-location:8000` (from Grafana)
- External access: `http://localhost:8000` (from host)
- **Status:** ✅ No changes needed

### Prometheus Integration

**Metrics Flow:**
1. Backend calculates POI ETAs based on telemetry
2. Backend exposes metrics: `starlink_eta_poi_seconds{name="POI-NAME"}`
3. Prometheus scrapes metrics every 1s (check prometheus.yml for interval)
4. Grafana queries Prometheus for ETA data
5. Grafana joins ETA data with POI metadata from API

**Changes Needed (Phase 1):**
- Ensure ETA metrics are updated every telemetry cycle
- Add POI metadata to metric labels (if feasible)
- Create `/api/pois/etas` endpoint to provide ETAs in structured format

---

## Current System State

### What's Working

✅ **Backend API:**
- POI CRUD endpoints fully functional
- POI storage in `/data/pois.json`
- API responds correctly to all operations

✅ **Grafana Map:**
- Geomap panel displays current position and route history
- Real-time updates every 1 second
- Tooltips enabled and working

✅ **ETA Calculations:**
- Backend has logic to calculate distance to POIs (Haversine formula)
- Prometheus metrics available: `starlink_eta_poi_seconds`, `starlink_distance_to_poi_meters`

### What's Not Working (Yet)

❌ **POI Markers on Map:**
- POI data not fetched in Grafana
- No POI markers layer configured

❌ **ETA Tooltips:**
- ETA data not joined to POI data
- Tooltips don't show POI information

❌ **POI Table View:**
- No dashboard or panel for POI table

❌ **POI Management UI:**
- No UI for creating/editing/deleting POIs
- Users must use API directly (curl, Postman, etc.)

### Known Issues

⚠️ **Issue 1: POI ETA Metric Updates**
- **Problem:** ETA metrics may not update if POI list changes dynamically
- **Impact:** New POIs won't have ETA metrics until backend restart
- **Solution (Phase 1):** Add POI watcher to update metrics when POIs are added/removed

⚠️ **Issue 2: Grafana Infinity Plugin Availability**
- **Problem:** Plugin may not be installed or available in deployed Grafana
- **Impact:** POI data cannot be fetched from API
- **Solution (Phase 2):** Check plugin availability, install if needed, or use alternative

⚠️ **Issue 3: CORS for POI Management UI**
- **Problem:** Iframe may be blocked by CORS/CSP policies
- **Impact:** POI management UI won't load in Grafana iframe
- **Solution (Phase 5):** Configure backend CORS headers, use same-origin proxy, or external link

---

## Testing Strategy

### Unit Tests

**Backend (pytest):**
- Test POI CRUD operations
- Test ETA calculation accuracy
- Test edge cases: zero speed, moving away from POI, very close approach
- Test file operations: read, write, corruption handling

**Location:**
- `backend/starlink-location/tests/test_poi_manager.py`
- `backend/starlink-location/tests/test_pois_api.py`
- `backend/starlink-location/tests/test_eta_calculation.py`

### Integration Tests

**Backend + Storage:**
- Create POI → verify in `/data/pois.json`
- Update POI → verify file updated
- Delete POI → verify removed from file
- Restart backend → verify POIs loaded correctly

**Backend + Prometheus:**
- Add POI → verify ETA metric appears
- Move terminal → verify ETA metric updates
- Delete POI → verify ETA metric removed

### End-to-End Tests

**Manual Testing (Simulation Mode):**
1. Start stack: `docker compose up -d`
2. Verify simulation running: `curl http://localhost:8000/health`
3. Create POI via API: `curl -X POST http://localhost:8000/api/pois -d '{"name":"Test","latitude":40.0,"longitude":-74.0}'`
4. Check Grafana map: POI marker visible
5. Hover POI: Tooltip shows ETA
6. Check POI table: POI listed with correct ETA
7. Edit POI via UI: Changes reflected on map
8. Delete POI via UI: POI removed from map and table

**Automated E2E (Future):**
- Use Playwright or Selenium to automate Grafana interactions
- Verify POI appears on map after API create
- Verify tooltip content
- Verify table updates

---

## Environment Setup

### Prerequisites

1. **Docker and Docker Compose:**
   - Version: Docker 20.10+, Compose 2.0+
   - Check: `docker --version && docker compose version`

2. **Git:**
   - For version control and feature branch management
   - Check: `git --version`

3. **Text Editor / IDE:**
   - VSCode (recommended for JSON/Python)
   - Extensions: Prettier (for JSON formatting)

### Initial Setup

1. **Clone repository:**
   ```bash
   cd /home/brian/Projects/starlink-dashboard-dev
   git checkout dev  # or main, depending on strategy
   ```

2. **Create feature branch:**
   ```bash
   git checkout -b feature/poi-interactive-management
   ```

3. **Start development stack:**
   ```bash
   docker compose up -d
   ```

4. **Verify services:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/pois
   # Open browser: http://localhost:3000 (Grafana)
   ```

5. **Check Grafana plugins:**
   - Navigate to: http://localhost:3000/plugins
   - Search for: "Infinity"
   - Install if not present

### Development Workflow

1. **Make changes to backend:**
   - Edit files in `backend/starlink-location/`
   - Rebuild container: `docker compose build starlink-location`
   - Restart service: `docker compose restart starlink-location`

2. **Make changes to Grafana dashboard:**
   - Edit `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
   - Restart Grafana: `docker compose restart grafana`
   - Refresh dashboard in browser

3. **Test changes:**
   - Use simulation mode: `STARLINK_MODE=simulation` in `.env`
   - Verify in browser and with curl

4. **Commit changes:**
   ```bash
   git add <files>
   git commit -m "feat: <description>"
   git push origin feature/poi-interactive-management
   ```

---

## Common Commands

### Backend API

```bash
# List POIs
curl http://localhost:8000/api/pois

# Get specific POI
curl http://localhost:8000/api/pois/{poi_id}

# Create POI
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Airport",
    "latitude": 40.6413,
    "longitude": -73.7781,
    "category": "airport",
    "icon": "airport"
  }'

# Update POI
curl -X PUT http://localhost:8000/api/pois/{poi_id} \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}'

# Delete POI
curl -X DELETE http://localhost:8000/api/pois/{poi_id}

# Get POI count
curl http://localhost:8000/api/pois/count/total
```

### Docker Commands

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# Rebuild backend
docker compose build starlink-location

# Restart backend
docker compose restart starlink-location

# View logs
docker compose logs -f starlink-location

# Check backend health
docker compose exec starlink-location curl http://localhost:8000/health
```

### Prometheus Queries

```bash
# Query ETA metrics
curl 'http://localhost:9090/api/v1/query?query=starlink_eta_poi_seconds'

# Query distance metrics
curl 'http://localhost:9090/api/v1/query?query=starlink_distance_to_poi_meters'
```

---

## Troubleshooting

### Issue: POI API returns 404

**Symptoms:** `curl http://localhost:8000/api/pois` returns 404

**Diagnosis:**
- Check if backend is running: `docker compose ps`
- Check backend logs: `docker compose logs starlink-location`
- Verify route registration in `main.py`

**Solution:**
- Ensure POI router is included in FastAPI app
- Check `main.py` for: `app.include_router(pois.router)`

---

### Issue: Grafana can't fetch POI data

**Symptoms:** Infinity data source shows error or no data

**Diagnosis:**
- Check Infinity plugin installed: Grafana → Plugins
- Check backend accessible from Grafana: `docker compose exec grafana curl http://starlink-location:8000/api/pois`
- Check CORS headers in backend

**Solution:**
- Install Infinity plugin if missing
- Verify Docker network allows Grafana → backend communication
- Add CORS headers to FastAPI if needed:
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(CORSMiddleware, allow_origins=["*"])
  ```

---

### Issue: ETA tooltips not updating

**Symptoms:** Tooltip shows outdated ETA values

**Diagnosis:**
- Check Grafana query refresh interval (should be 1s)
- Check Prometheus scrape interval (should be 1s)
- Check if ETA metrics are updating: `curl http://localhost:8000/metrics | grep starlink_eta_poi`

**Solution:**
- Set query interval to 1s in dashboard JSON
- Verify backend updates ETA metrics every telemetry cycle
- Check for backend errors in logs

---

### Issue: POI markers not visible on map

**Symptoms:** Map shows position but no POI markers

**Diagnosis:**
- Check POI layer configuration in dashboard JSON
- Check if POI data source returns data
- Check layer z-index and opacity

**Solution:**
- Verify layer `type: "markers"` and correct query reference
- Test data source independently in Grafana Explore
- Increase marker size or opacity for visibility

---

## Quick Reference

### POI JSON Structure

```json
{
  "id": "jfk-airport",
  "name": "JFK Airport",
  "latitude": 40.6413,
  "longitude": -73.7781,
  "icon": "airport",
  "category": "airport",
  "description": "John F. Kennedy International Airport",
  "route_id": null,
  "created_at": "2025-10-30T12:00:00Z",
  "updated_at": "2025-10-30T12:00:00Z"
}
```

### Grafana Geomap Layer (POI Markers)

```json
{
  "type": "markers",
  "name": "Points of Interest",
  "config": {
    "style": {
      "color": { "field": "eta_seconds", "mode": "field" },
      "size": { "fixed": 12, "mode": "fixed" },
      "symbol": { "field": "icon", "mode": "field" }
    },
    "showLegend": true
  },
  "location": {
    "mode": "coords",
    "latitude": "latitude",
    "longitude": "longitude"
  },
  "tooltip": true
}
```

### ETA Color Mapping

```javascript
// Grafana field override for color by ETA
{
  "matcher": { "id": "byName", "options": "eta_seconds" },
  "properties": [
    {
      "id": "color",
      "value": {
        "mode": "thresholds",
        "thresholds": [
          { "value": 0, "color": "red" },      // < 5 min
          { "value": 300, "color": "orange" },  // 5-15 min
          { "value": 900, "color": "yellow" },  // 15-60 min
          { "value": 3600, "color": "blue" }    // > 60 min
        ]
      }
    }
  ]
}
```

---

## Related Documentation

- **Main Plan:** `poi-interactive-management-plan.md`
- **Task Checklist:** `poi-interactive-management-tasks.md`
- **Project Design Doc:** `docs/design-document.md`
- **Development Plan:** `docs/phased-development-plan.md`
- **Project Instructions:** `CLAUDE.md`

---

**Document Status:** ✅ Complete and Ready for Reference

**Last Updated:** 2025-10-30
