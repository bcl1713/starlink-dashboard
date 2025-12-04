# POIs.py Refactoring Analysis

## File Overview

- **Current Location:**
  `/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/api/pois.py`
- **Current Size:** 1159 lines
- **Target Max Size:** 300 lines per module
- **Total Functions/Endpoints:** 13 items (9 endpoints + 4 helper functions)

---

## 1. ENDPOINTS (API Routes)

All endpoints are registered with `@router.get()`, `@router.post()`,
`@router.put()`, or `@router.delete()`.

### READ Endpoints (GET)

| Line | Endpoint                               | Function                 | Response Model       | Purpose                                             |
| ---- | -------------------------------------- | ------------------------ | -------------------- | --------------------------------------------------- |
| 156  | `GET /api/pois`                        | `list_pois()`            | `POIListResponse`    | List all POIs, optionally filtered by route/mission |
| 259  | `GET /api/pois/etas`                   | `get_pois_with_etas()`   | `POIETAListResponse` | Get all POIs with real-time ETA data                |
| 627  | `GET /api/pois/count/total`            | `count_pois()`           | `dict`               | Get total POI count                                 |
| 651  | `GET /api/pois/stats/next-destination` | `get_next_destination()` | `dict`               | Get closest POI name                                |
| 754  | `GET /api/pois/stats/next-eta`         | `get_next_eta()`         | `dict`               | Get ETA to closest POI                              |
| 857  | `GET /api/pois/stats/approaching`      | `get_approaching_pois()` | `dict`               | Get count of POIs within 30 minutes                 |
| 922  | `GET /api/pois/{poi_id}`               | `get_poi()`              | `POIResponse`        | Get specific POI by ID                              |

### WRITE Endpoints (POST/PUT/DELETE)

| Line | Endpoint                    | Function       | Response Model | Purpose             |
| ---- | --------------------------- | -------------- | -------------- | ------------------- |
| 979  | `POST /api/pois`            | `create_poi()` | `POIResponse`  | Create new POI      |
| 1057 | `PUT /api/pois/{poi_id}`    | `update_poi()` | `POIResponse`  | Update existing POI |
| 1132 | `DELETE /api/pois/{poi_id}` | `delete_poi()` | `None`         | Delete POI          |

**Total Endpoints:** 10 (7 read + 3 write)

---

## 2. HELPER FUNCTIONS

### Math/Navigation Helpers

| Line | Function                    | Lines            | Input                  | Output         | Purpose                                                              |
| ---- | --------------------------- | ---------------- | ---------------------- | -------------- | -------------------------------------------------------------------- |
| 40   | `calculate_bearing()`       | 40-65 (26 lines) | lat1, lon1, lat2, lon2 | float (0-360°) | Calculate bearing between two points                                 |
| 68   | `calculate_course_status()` | 68-95 (28 lines) | heading, bearing       | str            | Determine course status (on_course, slightly_off, off_track, behind) |

### Status Calculation

| Line | Function                         | Lines             | Input              | Output | Purpose                                           |
| ---- | -------------------------------- | ----------------- | ------------------ | ------ | ------------------------------------------------- |
| 98   | `_calculate_poi_active_status()` | 98-153 (56 lines) | poi, route_manager | bool   | Calculate if POI is active based on route/mission |

### Module Setup

| Line | Function            | Lines           | Input       | Output | Purpose                          |
| ---- | ------------------- | --------------- | ----------- | ------ | -------------------------------- |
| 30   | `set_coordinator()` | 30-33 (4 lines) | coordinator | None   | Set global coordinator reference |

**Total Helpers:** 4 functions (98 lines total)

---

## 3. DEPENDENCY ANALYSIS

### Function Call Graph

```text
┌─────────────────────────────────────────────────────────────────┐
│ GLOBAL STATE                                                    │
├─────────────────────────────────────────────────────────────────┤
│ _coordinator: Optional[object]                                  │
│ set_coordinator(coordinator) → sets _coordinator               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ MATH/NAVIGATION HELPERS (No external dependencies)              │
├─────────────────────────────────────────────────────────────────┤
│ calculate_bearing(lat1, lon1, lat2, lon2)                       │
│   ├─ Uses: math.radians(), math.sin(), math.cos(), math.atan2()│
│   └─ Used By: get_pois_with_etas()                              │
│                                                                  │
│ calculate_course_status(heading, bearing)                       │
│   ├─ Uses: abs()                                                │
│   └─ Used By: get_pois_with_etas()                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ STATUS HELPERS (POI Manager + Route Manager)                    │
├─────────────────────────────────────────────────────────────────┤
│ _calculate_poi_active_status(poi, route_manager)                │
│   ├─ Uses: Path(), load_mission()                               │
│   └─ Used By:                                                   │
│       ├─ list_pois() [lines 224-227]                            │
│       ├─ get_pois_with_etas() [lines 579-582]                   │
│       ├─ get_poi() [lines 954-957]                              │
│       ├─ create_poi() [lines 1027-1030]                         │
│       └─ update_poi() [lines 1100-1103]                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CRUD ENDPOINTS (POI Manager)                                    │
├─────────────────────────────────────────────────────────────────┤
│ list_pois() [156-256]                                           │
│   ├─ POI Manager: poi_manager.list_pois()                       │
│   ├─ Route Manager: route_manager.*                             │
│   ├─ Helpers: _calculate_poi_active_status()                    │
│   └─ Complexity: Medium (filtering logic)                       │
│                                                                  │
│ get_poi() [922-976]                                             │
│   ├─ POI Manager: poi_manager.get_poi()                         │
│   ├─ Route Manager: route_manager.*                             │
│   ├─ Helpers: _calculate_poi_active_status()                    │
│   └─ Complexity: Low                                            │
│                                                                  │
│ create_poi() [979-1054]                                         │
│   ├─ POI Manager: poi_manager.create_poi()                      │
│   ├─ Coordinator: _coordinator.route_manager                    │
│   ├─ Helpers: _calculate_poi_active_status()                    │
│   └─ Complexity: Low                                            │
│                                                                  │
│ update_poi() [1057-1129]                                        │
│   ├─ POI Manager: poi_manager.update_poi()                      │
│   ├─ Route Manager: route_manager.*                             │
│   ├─ Helpers: _calculate_poi_active_status()                    │
│   └─ Complexity: Low                                            │
│                                                                  │
│ delete_poi() [1132-1159]                                        │
│   ├─ POI Manager: poi_manager.delete_poi()                      │
│   └─ Complexity: Low                                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ETA ENDPOINT (Complex, 365+ lines)                              │
├─────────────────────────────────────────────────────────────────┤
│ get_pois_with_etas() [259-624] - 365 lines                      │
│   ├─ Coordinator: _coordinator.get_current_telemetry()          │
│   ├─ Route Manager: route_manager.get_active_route()            │
│   ├─ POI Manager: poi_manager.list_pois()                       │
│   ├─ ETA Service: get_eta_calculator()                          │
│   ├─ Flight State: get_flight_state_manager()                   │
│   ├─ Helpers:                                                   │
│   │   ├─ calculate_bearing()                                    │
│   │   ├─ calculate_course_status()                              │
│   │   └─ _calculate_poi_active_status()                         │
│   ├─ Complex Logic:                                             │
│   │   ├─ Telemetry extraction (40 lines)                        │
│   │   ├─ Parameter parsing (40 lines)                           │
│   │   ├─ Route progress calculation (15 lines)                  │
│   │   ├─ Status/Category filtering (10 lines)                   │
│   │   ├─ POI loop with ETA calculations (160 lines)             │
│   │   └─ Sorting (3 lines)                                      │
│   └─ Complexity: VERY HIGH                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ STATS ENDPOINTS (Similar patterns, duplicated code)             │
├─────────────────────────────────────────────────────────────────┤
│ get_next_destination() [651-751] - 101 lines                    │
│   ├─ Coordinator: _coordinator.get_current_telemetry()          │
│   ├─ POI Manager: poi_manager.list_pois()                       │
│   ├─ ETA Service: get_eta_calculator()                          │
│   ├─ Flight State: get_flight_state_manager()                   │
│   └─ Duplicated: Telemetry extraction (similar to others)       │
│                                                                  │
│ get_next_eta() [754-854] - 101 lines                            │
│   ├─ Coordinator: _coordinator.get_current_telemetry()          │
│   ├─ POI Manager: poi_manager.list_pois()                       │
│   ├─ ETA Service: get_eta_calculator()                          │
│   ├─ Flight State: get_flight_state_manager()                   │
│   └─ Duplicated: Telemetry extraction (identical code)          │
│                                                                  │
│ get_approaching_pois() [857-919] - 63 lines                     │
│   ├─ POI Manager: poi_manager.list_pois()                       │
│   ├─ ETA Service: get_eta_calculator()                          │
│   └─ Coordinator: _coordinator.get_current_telemetry()          │
│                                                                  │
│ count_pois() [627-648] - 22 lines                               │
│   └─ POI Manager: poi_manager.count_pois()                      │
└─────────────────────────────────────────────────────────────────┘
```

### External Dependencies

```text
IMPORTS:
├─ logging
├─ math
├─ pathlib.Path
├─ typing.Optional
├─ fastapi (APIRouter, HTTPException, Query, status, Depends)
│
MODELS:
├─ app.models.poi (POI, POICreate, POIETAListResponse, POIListResponse, POIResponse, POIUpdate, POIWithETA)
├─ app.models.flight_status (ETAMode, FlightPhase)
│
SERVICES (Injected via Depends):
├─ app.services.poi_manager.POIManager
├─ app.services.route_manager.RouteManager
├─ app.services.route_eta_calculator.RouteETACalculator
├─ app.services.flight_state_manager.get_flight_state_manager()
├─ app.core.eta_service.get_eta_calculator()
│
UTILITIES:
├─ app.mission.storage.load_mission()
├─ app.mission.dependencies (get_route_manager, get_poi_manager)
│
GLOBAL STATE:
└─ _coordinator: Optional[object] (set via set_coordinator())
```

---

## 4. CODE PATTERNS & DUPLICATION

### Telemetry Extraction Pattern (DUPLICATED 3x)

**Lines:** 675-694, 782-801, 881-900 **Pattern:**

```python
try:
    if _coordinator:
        try:
            telemetry = _coordinator.get_current_telemetry()
            lat = telemetry.position.latitude
            lon = telemetry.position.longitude
            speed = telemetry.position.speed
        except Exception:
            lat = float(latitude) if latitude else 41.6
            lon = float(longitude) if longitude else -74.0
            speed = float(speed_knots) if speed_knots else 67.0
    else:
        lat = float(latitude) if latitude else 41.6
        lon = float(longitude) if longitude else -74.0
        speed = float(speed_knots) if speed_knots else 67.0
except (ValueError, TypeError):
    lat, lon, speed = 41.6, -74.0, 67.0
```

**Can be extracted to:** `helpers.extract_telemetry()`

### Flight State Snapshot Pattern (DUPLICATED 3x)

**Lines:** 706-713, 736-743, 812-820, 839-848 **Pattern:**

```python
status_eta_mode = "estimated"
status_phase = None
try:
    from app.services.flight_state_manager import get_flight_state_manager
    snapshot = get_flight_state_manager().get_status()
    status_eta_mode = snapshot.eta_mode.value
    status_phase = snapshot.phase.value
except Exception:
    pass
```

**Can be extracted to:** `helpers.get_flight_state_snapshot()`

### POI Response Construction (DUPLICATED 5x)

**Lines:** 234-251, 959-976, 1032-1048, 1105-1121 **Pattern:**

```python
POIResponse(
    id=poi.id,
    name=poi.name,
    latitude=poi.latitude,
    longitude=poi.longitude,
    icon=poi.icon,
    category=poi.category,
    active=active_status,
    description=poi.description,
    route_id=poi.route_id,
    mission_id=poi.mission_id,
    created_at=poi.created_at,
    updated_at=poi.updated_at,
    projected_latitude=poi.projected_latitude,
    projected_longitude=poi.projected_longitude,
    projected_waypoint_index=poi.projected_waypoint_index,
    projected_route_progress=poi.projected_route_progress,
)
```

**Can be extracted to:** `converters.poi_to_response()`

### Closest POI Finding Pattern (DUPLICATED 2x)

**Lines:** 725-733, 831-837 **Pattern:**

```python
closest = None
closest_eta = float("inf")

for poi in pois:
    distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
    eta_seconds = eta_calc.calculate_eta(distance, speed)
    if eta_seconds < closest_eta:
        closest_eta = eta_seconds
        closest = poi
```

**Can be extracted to:** `helpers.find_closest_poi()`

---

## 5. GROUPING: Logical Module Structure

Based on analysis, here's the optimal grouping:

### Module A: CRUD Operations (`pois/crud.py`) - ~220 lines

**Purpose:** Core POI create, read, update, delete operations **Functions:**

- `list_pois()` - list all POIs with filters
- `get_poi()` - get single POI
- `create_poi()` - create new POI
- `update_poi()` - update POI
- `delete_poi()` - delete POI
- `count_pois()` - count POIs
- `_calculate_poi_active_status()` - determine if POI is active

**Dependencies:**

- POIManager (Depends)
- RouteManager (Depends)
- \_coordinator (global)
- POIResponse, POIListResponse (models)
- POICreate, POIUpdate (models)

**Reasoning:** These are cohesive CRUD operations that work directly with POI
management.

### Module B: ETA Calculations (`pois/etas.py`) - ~280 lines

**Purpose:** Real-time ETA and distance calculations with flight state
integration **Functions:**

- `get_pois_with_etas()` - calculate ETA for all POIs

**Dependencies:**

- RouteManager (Depends)
- POIManager (Depends)
- ETACalculator (service)
- FlightStateManager (service)
- RouteETACalculator (service)
- POIETAListResponse (model)
- POIWithETA (model)
- `calculate_bearing()` - import from helpers
- `calculate_course_status()` - import from helpers
- `_calculate_poi_active_status()` - import from crud

**Reasoning:** Large, complex endpoint that combines multiple concerns (ETA,
flight state, route awareness).

### Module C: Statistics Endpoints (`pois/stats.py`) - ~230 lines

**Purpose:** Aggregate POI statistics (next destination, approaching count,
etc.) **Functions:**

- `get_next_destination()` - closest POI name
- `get_next_eta()` - ETA to closest POI
- `get_approaching_pois()` - count POIs within 30 min threshold
- (keep `count_pois()` here or in crud - RECOMMEND HERE for stats context)

**Dependencies:**

- POIManager (Depends)
- \_coordinator (global)
- ETACalculator (service)
- FlightStateManager (service)
- `extract_telemetry()` - import from helpers
- `get_flight_state_snapshot()` - import from helpers
- `find_closest_poi()` - import from helpers

**Reasoning:** These are aggregate statistics endpoints with similar patterns.

### Module D: Helpers & Utilities (`pois/helpers.py`) - ~150 lines

**Purpose:** Reusable math, navigation, and utility functions **Functions:**

- `calculate_bearing()` - math: bearing between two points
- `calculate_course_status()` - categorize heading vs bearing
- `extract_telemetry()` - EXTRACTED from crud/stats duplication
- `get_flight_state_snapshot()` - EXTRACTED from stats duplication
- `find_closest_poi()` - EXTRACTED from stats duplication
- `poi_to_response()` - EXTRACTED from response construction duplication

**Dependencies:**

- math (stdlib)
- POIResponse (model)
- ETACalculator (service)
- FlightStateManager (service)

**Reasoning:** Pure functions with no endpoint concerns. Reusable across
modules.

### Module E: Router & Initialization (`pois/__init__.py`) - ~50 lines

**Purpose:** Create and configure the POI API router with all endpoints
**Contents:**

- `set_coordinator()` - global coordinator setter
- `router` - APIRouter instance
- Import and register all endpoints from submodules

**Reasoning:** Central place to compose the API, matching the routes/ pattern.

---

## 6. PROPOSED MODULE STRUCTURE

```text
backend/starlink-location/app/api/pois/
├── __init__.py              (50 lines)  Main router, set_coordinator
├── crud.py                  (220 lines) CRUD endpoints + active status
├── etas.py                  (280 lines) ETA endpoint (get_pois_with_etas)
├── stats.py                 (230 lines) Stats endpoints
└── helpers.py               (150 lines) Math, telemetry, extraction helpers
```

**Total Estimated Lines:** ~930 lines (vs 1159 currently = 20% reduction +
clarity)

---

## 7. DEPENDENCY IMPORT MAP

### `pois/__init__.py`

```python
from fastapi import APIRouter
from app.mission.dependencies import get_route_manager, get_poi_manager

# Import router functions
from .crud import router as crud_router
from .etas import router as etas_router
from .stats import router as stats_router

# Main router
router = APIRouter(prefix="/api/pois", tags=["pois"])

# Include sub-routers
router.include_router(crud_router)
router.include_router(etas_router)
router.include_router(stats_router)

# Global coordinator
_coordinator = None
def set_coordinator(coordinator):
    global _coordinator
    _coordinator = coordinator
```

### `pois/helpers.py`

```python
import logging
import math
from typing import Optional, Tuple

from app.models.poi import POI, POIResponse
from app.core.eta_service import get_eta_calculator
from app.services.flight_state_manager import get_flight_state_manager
from app.models.flight_status import ETAMode, FlightPhase

# Functions: calculate_bearing, calculate_course_status,
#           extract_telemetry, get_flight_state_snapshot,
#           find_closest_poi, poi_to_response
```

### `pois/crud.py`

```python
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.models.poi import POI, POICreate, POIResponse, POIUpdate, POIListResponse
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.mission.storage import load_mission
from app.mission.dependencies import get_route_manager, get_poi_manager

from .helpers import _calculate_poi_active_status, poi_to_response

router = APIRouter()

# Functions: list_pois, get_poi, create_poi, update_poi,
#           delete_poi, count_pois, _calculate_poi_active_status
```

### `pois/etas.py`

```python
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.models.poi import POIETAListResponse, POIWithETA
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.services.route_eta_calculator import RouteETACalculator
from app.core.eta_service import get_eta_calculator
from app.services.flight_state_manager import get_flight_state_manager
from app.models.flight_status import ETAMode, FlightPhase
from app.mission.dependencies import get_route_manager, get_poi_manager

from .helpers import (
    calculate_bearing,
    calculate_course_status,
    _calculate_poi_active_status,
)

router = APIRouter()

# Functions: get_pois_with_etas
```

### `pois/stats.py`

```python
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.services.poi_manager import POIManager
from app.mission.dependencies import get_poi_manager

from .helpers import (
    extract_telemetry,
    get_flight_state_snapshot,
    find_closest_poi,
)

router = APIRouter()

# Functions: count_pois, get_next_destination, get_next_eta,
#           get_approaching_pois
```

---

## 8. ENDPOINT DISTRIBUTION IN NEW MODULES

| Module       | Endpoint | Method                             | Path                     | Function |
| ------------ | -------- | ---------------------------------- | ------------------------ | -------- |
| **crud.py**  | GET      | `/api/pois`                        | `list_pois()`            |
| **crud.py**  | GET      | `/api/pois/{poi_id}`               | `get_poi()`              |
| **crud.py**  | POST     | `/api/pois`                        | `create_poi()`           |
| **crud.py**  | PUT      | `/api/pois/{poi_id}`               | `update_poi()`           |
| **crud.py**  | DELETE   | `/api/pois/{poi_id}`               | `delete_poi()`           |
| **stats.py** | GET      | `/api/pois/count/total`            | `count_pois()`           |
| **stats.py** | GET      | `/api/pois/stats/next-destination` | `get_next_destination()` |
| **stats.py** | GET      | `/api/pois/stats/next-eta`         | `get_next_eta()`         |
| **stats.py** | GET      | `/api/pois/stats/approaching`      | `get_approaching_pois()` |
| **etas.py**  | GET      | `/api/pois/etas`                   | `get_pois_with_etas()`   |

---

## 9. CODE MIGRATION CHECKLIST

### Phase 1: Create New Module Structure

- [ ] Create `/app/api/pois/` directory
- [ ] Create `__init__.py` with router composition
- [ ] Create `helpers.py` with extracted functions

### Phase 2: Create CRUD Module

- [ ] Create `crud.py`
- [ ] Move CRUD endpoints (list_pois, get_poi, create_poi, update_poi,
      delete_poi)
- [ ] Move `_calculate_poi_active_status()` helper
- [ ] Update imports

### Phase 3: Create ETA Module

- [ ] Create `etas.py`
- [ ] Move `get_pois_with_etas()` endpoint
- [ ] Update imports to use helpers

### Phase 4: Create Stats Module

- [ ] Create `stats.py`
- [ ] Move stats endpoints (count_pois, get_next_destination, get_next_eta,
      get_approaching_pois)
- [ ] Update imports to use helpers

### Phase 5: Update Main App

- [ ] Update `/app/main.py` or router initialization to include new module
      router
- [ ] Ensure `set_coordinator()` is accessible from new location
- [ ] Test all endpoints

### Phase 6: Cleanup

- [ ] Remove old `pois.py` file
- [ ] Verify no remaining imports from old location
- [ ] Run test suite

---

## 10. REFACTORING BENEFITS

### Before (1159 lines)

- Single monolithic file
- Mixed concerns (CRUD, ETA, stats, math)
- Code duplication (telemetry extraction, flight state snapshot)
- Hard to test individual concerns
- Difficult to modify without affecting everything

### After (~930 lines total)

- **Separation of Concerns:** CRUD, ETA, Stats, Helpers
- **Reduced Duplication:** Shared helpers extracted
- **Better Testability:** Each module has clear responsibilities
- **Easier Maintenance:** Changes to one concern don't affect others
- **Improved Readability:** Each file <300 lines
- **Reusable Code:** Helpers can be imported by other modules
- **Scalability:** Easy to add new endpoints to appropriate module

### Estimated Time Savings

- Development: Faster to locate and modify code
- Testing: Clearer which tests apply to which module
- Debugging: Smaller scope to search when errors occur
- Onboarding: New developers understand structure faster
