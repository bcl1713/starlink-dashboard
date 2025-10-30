# POI Interactive Management Feature

**Status:** 🟡 Planning Complete - Ready for Implementation

**Feature Branch:** `feature/poi-interactive-management`

**Created:** 2025-10-30

---

## Quick Links

- **[Strategic Plan](./poi-interactive-management-plan.md)** - Comprehensive implementation plan with architecture, phases, and risk assessment
- **[Context Document](./poi-interactive-management-context.md)** - Key files, decisions, dependencies, and troubleshooting
- **[Task Checklist](./poi-interactive-management-tasks.md)** - Detailed task list with acceptance criteria and progress tracking

---

## Feature Overview

This feature adds interactive Points of Interest (POI) management to the Starlink dashboard, allowing users to:

1. **View POI markers** on the map with labels and icons
2. **Hover for ETA tooltips** showing time-to-arrival, distance, and bearing
3. **Manage POIs** through a user-friendly interface (create, edit, delete)
4. **View POI table** with real-time ETA information and sorting
5. **Color-coded indicators** showing proximity (red = imminent, blue = distant)

---

## Implementation Phases

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| 0 | Setup & Planning | 0.5 days | ✅ Complete |
| 1 | Backend ETA Integration | 2-3 days | 🟡 Not Started |
| 2 | Grafana POI Markers Layer | 2-3 days | 🟡 Not Started |
| 3 | Interactive ETA Tooltips | 2-3 days | 🟡 Not Started |
| 4 | POI Table View Dashboard | 1-2 days | 🟡 Not Started |
| 5 | POI Management UI | 4-5 days | 🟡 Not Started |
| 6 | Testing & Refinement | 2-3 days | 🟡 Not Started |
| 7 | Feature Branch & Deployment | 1 day | 🟡 Not Started |

**Total Estimated Duration:** 15-20 days (3-4 weeks)

**Accelerated (Parallel):** 10-14 days (2-3 weeks)

---

## Key Features

### POI Markers on Map
- Display POI markers on fullscreen overview map
- Custom icons based on category (airport, city, landmark, etc.)
- Labels showing POI names
- Clickable for more information

### Real-time ETA Tooltips
- Hover over POI to see:
  - POI name and category
  - Estimated time of arrival (e.g., "15 minutes")
  - Distance (meters or kilometers)
  - Bearing/direction
- Updates every second as terminal moves
- Color-coded by proximity:
  - 🔴 Red: < 5 minutes (imminent)
  - 🟠 Orange: 5-15 minutes (approaching)
  - 🟡 Yellow: 15-60 minutes (near-term)
  - 🔵 Blue: > 60 minutes (distant)

### POI Management UI
- Create new POIs with:
  - Name, coordinates (lat/lon)
  - Category and icon
  - Optional description
  - Click-to-place on map
- Edit existing POIs
- Delete POIs with confirmation
- Real-time sync to map and table

### POI Table View
- Live-updating table showing all POIs
- Columns: Name, Category, Lat/Lon, Distance, ETA, Arrival Time
- Sortable by ETA (closest first), name, category
- Filterable by category
- "Next POI" countdown timer

---

## Current State

### What Already Exists ✅

- **Backend POI API:** Full CRUD operations (`/api/pois`)
- **POI Data Models:** Well-structured Pydantic models
- **POI Storage:** File-based JSON storage (`/data/pois.json`)
- **ETA Metrics:** Prometheus metrics for distance and ETA
- **Grafana Map:** Geomap with position and route history

### What's Missing ❌

- POI markers layer on Grafana map
- ETA tooltips on hover
- POI management user interface
- POI table view dashboard
- Real-time ETA calculations integrated with map
- Color-coding by proximity

---

## Technical Stack

### Backend
- **Language:** Python 3.x
- **Framework:** FastAPI
- **Storage:** JSON file (`/data/pois.json`)
- **Metrics:** Prometheus client
- **New Dependencies:** Jinja2 (for UI templates), Leaflet.js (for map widget)

### Frontend
- **Platform:** Grafana 11.1.0+
- **Data Sources:** Prometheus, Infinity plugin (or alternative)
- **Plugins:** Geomap, Table, Infinity (or SimpleJSON/HTTP API)

### Infrastructure
- **Deployment:** Docker Compose
- **Volumes:** `/data` for POI persistence
- **Network:** Bridge network (starlink-location ↔ grafana)

---

## Getting Started

### Prerequisites

1. **Development Environment:**
   - Docker and Docker Compose installed
   - Git for version control
   - Text editor (VSCode recommended)

2. **Grafana Plugin:**
   - Infinity plugin (check availability at http://localhost:3000/plugins)
   - Alternative: SimpleJSON or HTTP API data source

### Quick Start

1. **Review the Plan:**
   ```bash
   # Read the strategic plan
   cat poi-interactive-management-plan.md
   ```

2. **Create Feature Branch:**
   ```bash
   git checkout dev  # or main
   git checkout -b feature/poi-interactive-management
   git push -u origin feature/poi-interactive-management
   ```

3. **Start Development Stack:**
   ```bash
   cd /home/brian/Projects/starlink-dashboard-dev
   docker compose up -d
   ```

4. **Verify Services:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/pois
   # Open browser: http://localhost:3000
   ```

5. **Begin Implementation:**
   - Start with Phase 1: Backend ETA Integration
   - Follow task checklist in `poi-interactive-management-tasks.md`
   - Update checklist as you complete tasks

---

## Development Workflow

1. **Read Context Document:** Understand key files and integration points
2. **Select Phase/Task:** Pick next task from checklist
3. **Implement:** Make changes to code
4. **Test:** Verify changes work (simulation mode recommended)
5. **Document:** Update task checklist and notes
6. **Commit:** Commit changes with descriptive message
7. **Repeat:** Move to next task

### Testing

- **Use Simulation Mode:** Set `STARLINK_MODE=simulation` in `.env`
- **Create Test POIs:** Use API to create sample POIs for testing
- **Verify on Map:** Check Grafana dashboard after each change
- **Check Logs:** Monitor backend logs for errors

---

## Key Files to Modify

### Backend
- `backend/starlink-location/app/core/metrics.py` - ETA metric updates
- `backend/starlink-location/app/api/pois.py` - Add `/api/pois/etas` endpoint
- `backend/starlink-location/main.py` - Register POI UI route (Phase 5)
- Create: `backend/starlink-location/templates/poi_ui.html` - POI management UI

### Frontend
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` - Add POI layer
- Create: `monitoring/grafana/provisioning/dashboards/poi-management.json` - POI table (optional)
- `monitoring/grafana/provisioning/datasources/` - Add Infinity data source config (if needed)

---

## Success Metrics

### Functional
- ✅ All POIs display on map with correct coordinates (100% accuracy)
- ✅ ETA calculations within ±10% of actual arrival time
- ✅ ETA tooltips refresh within 3 seconds
- ✅ All CRUD operations succeed without errors
- ✅ Dashboard loads in < 2 seconds with 50 POIs

### User Experience
- ✅ New users can add POI in < 60 seconds
- ✅ POI markers distinguishable at all zoom levels
- ✅ Tooltip provides essential info without clutter
- ✅ Users can find target POI in table in < 10 seconds

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Grafana Infinity plugin not available | Use SimpleJSON or HTTP API data source |
| ETA calculation inaccurate | Use moving average, configurable threshold |
| UI iframe blocked by CORS | Configure backend headers, use proxy |
| Performance issues with many POIs | Implement clustering, pagination, filtering |

---

## Future Enhancements (Out of Scope)

- POI alerts (approaching warnings)
- POI import/export (KML, GPX)
- Route-based ETA (along planned route)
- POI clustering at low zoom
- POI history (track arrivals)
- Multi-user collaboration
- Mobile app for POI management
- Voice alerts

---

## Support and Documentation

- **Project Docs:** `docs/design-document.md`, `docs/phased-development-plan.md`
- **Project Instructions:** `CLAUDE.md`
- **Troubleshooting:** See context document section on troubleshooting
- **API Reference:** Backend exposes OpenAPI docs at http://localhost:8000/docs

---

## Contact and Feedback

For questions, issues, or feedback during implementation:

1. Update task checklist with blockers
2. Document decisions in context document
3. Add notes to this README as needed

---

**Status:** ✅ Planning Complete - Ready to Begin Implementation

**Next Steps:**
1. Create feature branch
2. Begin Phase 1: Backend ETA Integration
3. Follow task checklist sequentially

**Last Updated:** 2025-10-30
