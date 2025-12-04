# POIs Refactoring - Detailed Dependency Diagrams

## 1. CURRENT FILE STRUCTURE & CALL GRAPH

### Current Single File

```text
pois.py (1159 lines)
├── Global State
│   └── _coordinator: Optional[object]
│
├── Configuration
│   ├── set_coordinator(coordinator)
│   └── router = APIRouter(prefix="/api/pois", tags=["pois"])
│
├── Helper Functions (98 lines)
│   ├── calculate_bearing(lat1, lon1, lat2, lon2) → float
│   ├── calculate_course_status(heading, bearing) → str
│   └── _calculate_poi_active_status(poi, route_manager) → bool
│
└── API Endpoints (1061 lines)
    ├── READ Endpoints
    │   ├── list_pois() [156-256]
    │   ├── get_pois_with_etas() [259-624] ⚠️ LARGE (365 lines)
    │   ├── get_poi() [922-976]
    │   ├── count_pois() [627-648]
    │   ├── get_next_destination() [651-751]
    │   ├── get_next_eta() [754-854]
    │   └── get_approaching_pois() [857-919]
    │
    └── WRITE Endpoints
        ├── create_poi() [979-1054]
        ├── update_poi() [1057-1129]
        └── delete_poi() [1132-1159]
```

---

## 2. NEW MODULE STRUCTURE

### Proposed Organization

```text
app/api/pois/
├── __init__.py (50 lines)
│   ├── router = APIRouter(prefix="/api/pois", tags=["pois"])
│   ├── set_coordinator(coordinator)
│   └── include_router() for crud, etas, stats
│
├── helpers.py (150 lines)
│   ├── Pure Functions
│   ├── Conversions
│   └── Utilities
│
├── crud.py (220 lines)
│   ├── CRUD Endpoints
│   └── Status Calculation
│
├── etas.py (280 lines)
│   └── ETA Calculation Endpoint
│
└── stats.py (230 lines)
    └── Statistics Endpoints
```

---

## 3. INTERNAL DEPENDENCIES BY MODULE

### helpers.py (Dependencies) ↓

```text
┌─────────────────────────────────────────────────────────────┐
│ helpers.py - FOUNDATION LAYER (150 lines)                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ External Dependencies (IMPORTS):                            │
│ ├─ logging                                                  │
│ ├─ math                                                     │
│ ├─ typing.Optional, Tuple                                   │
│ ├─ pathlib.Path                                             │
│ ├─ app.models.poi (POI, POIResponse)                        │
│ ├─ app.models.flight_status (ETAMode, FlightPhase)          │
│ ├─ app.core.eta_service (get_eta_calculator)                │
│ ├─ app.services.flight_state_manager                        │
│ ├─ app.mission.storage (load_mission)                       │
│ └─ app.services.route_manager (RouteManager)                │
│                                                              │
│ Functions (NEW/EXTRACTED):                                  │
│ │                                                            │
│ ├─ calculate_bearing(lat1, lon1, lat2, lon2) → float        │
│ │  Uses: math.radians, math.sin, math.cos, math.atan2      │
│ │  Pure Function (no state, no IO)                          │
│ │                                                            │
│ ├─ calculate_course_status(heading, bearing) → str          │
│ │  Uses: abs()                                              │
│ │  Pure Function (no state, no IO)                          │
│ │                                                            │
│ ├─ _calculate_poi_active_status(poi, route_manager) → bool  │
│ │  Uses: Path(), load_mission()                             │
│ │  Side Effects: logging                                    │
│ │  Used by: crud.py, etas.py                                │
│ │                                                            │
│ ├─ extract_telemetry(                                       │
│ │    _coordinator,                                          │
│ │    latitude: Optional[str],                               │
│ │    longitude: Optional[str],                              │
│ │    speed_knots: Optional[str]                             │
│ │  ) → Tuple[float, float, float]  [NEW - EXTRACTED]        │
│ │  Handles: Coordinator fallback + parameter parsing        │
│ │  Used by: stats.py                                        │
│ │                                                            │
│ ├─ get_flight_state_snapshot() → dict  [NEW - EXTRACTED]    │
│ │  Handles: Flight state retrieval with defaults            │
│ │  Returns: {"eta_mode": str, "flight_phase": Optional[str]}│
│ │  Used by: stats.py                                        │
│ │                                                            │
│ ├─ find_closest_poi(                                        │
│ │    pois: List[POI],                                       │
│ │    lat: float,                                            │
│ │    lon: float,                                            │
│ │    speed: float,                                          │
│ │    eta_calc                                               │
│ │  ) → Tuple[Optional[POI], float]  [NEW - EXTRACTED]       │
│ │  Returns: (closest_poi, closest_eta_seconds)              │
│ │  Used by: stats.py                                        │
│ │                                                            │
│ └─ poi_to_response(poi: POI, active_status: bool)           │
│    → POIResponse  [NEW - EXTRACTED]                         │
│    Handles: POI → POIResponse conversion (used 5x)          │
│    Used by: crud.py                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### crud.py (Dependencies) ↓

```text
┌─────────────────────────────────────────────────────────────┐
│ crud.py - CRUD OPERATIONS (220 lines)                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Imports from helpers.py:                                    │
│ ├─ _calculate_poi_active_status(poi, route_manager)         │
│ └─ poi_to_response(poi, active_status)                      │
│                                                              │
│ Imports from fastapi:                                       │
│ ├─ APIRouter                                                │
│ ├─ HTTPException, status                                    │
│ ├─ Query, Depends                                           │
│                                                              │
│ Imports from app.models:                                    │
│ ├─ POI, POICreate, POIUpdate                                │
│ ├─ POIResponse, POIListResponse                             │
│                                                              │
│ Imports from app.services:                                  │
│ ├─ POIManager (Depends injection)                           │
│ ├─ RouteManager (Depends injection)                         │
│                                                              │
│ Endpoints:                                                  │
│ │                                                            │
│ ├─ GET /api/pois                                            │
│ │  Function: list_pois()                                    │
│ │  Deps: route_manager, poi_manager                         │
│ │  Filters: route_id, mission_id, active_only              │
│ │  Returns: POIListResponse                                 │
│ │  Uses: _calculate_poi_active_status()                     │
│ │        poi_to_response() [implicit in response building]  │
│ │                                                            │
│ ├─ GET /api/pois/{poi_id}                                   │
│ │  Function: get_poi()                                      │
│ │  Deps: route_manager, poi_manager                         │
│ │  Returns: POIResponse                                     │
│ │  Uses: _calculate_poi_active_status()                     │
│ │        poi_to_response()                                  │
│ │                                                            │
│ ├─ POST /api/pois                                           │
│ │  Function: create_poi()                                   │
│ │  Deps: route_manager, poi_manager                         │
│ │  Body: POICreate                                          │
│ │  Returns: POIResponse                                     │
│ │  Uses: _coordinator.route_manager                         │
│ │        _calculate_poi_active_status()                     │
│ │        poi_to_response()                                  │
│ │                                                            │
│ ├─ PUT /api/pois/{poi_id}                                   │
│ │  Function: update_poi()                                   │
│ │  Deps: route_manager, poi_manager                         │
│ │  Body: POIUpdate                                          │
│ │  Returns: POIResponse                                     │
│ │  Uses: _calculate_poi_active_status()                     │
│ │        poi_to_response()                                  │
│ │                                                            │
│ ├─ DELETE /api/pois/{poi_id}                                │
│ │  Function: delete_poi()                                   │
│ │  Deps: poi_manager                                        │
│ │  Returns: None (204 No Content)                           │
│ │  Uses: POI Manager directly                               │
│ │                                                            │
│ └─ GET /api/pois/count/total  ⚠️ MAYBE HERE OR stats.py   │
│    Function: count_pois()                                   │
│    Deps: poi_manager                                        │
│    Returns: {"count": int}                                  │
│    Uses: POI Manager directly                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### etas.py (Dependencies) ↓

```text
┌─────────────────────────────────────────────────────────────┐
│ etas.py - ETA CALCULATIONS (280 lines) ⚠️ COMPLEX          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Imports from helpers.py:                                    │
│ ├─ calculate_bearing(lat1, lon1, lat2, lon2)                │
│ ├─ calculate_course_status(heading, bearing)                │
│ └─ _calculate_poi_active_status(poi, route_manager)         │
│                                                              │
│ Imports from fastapi:                                       │
│ ├─ APIRouter                                                │
│ ├─ HTTPException, status                                    │
│ ├─ Query, Depends                                           │
│                                                              │
│ Imports from app.models:                                    │
│ ├─ POIWithETA, POIETAListResponse                           │
│                                                              │
│ Imports from app.services:                                  │
│ ├─ POIManager (Depends)                                     │
│ ├─ RouteManager (Depends)                                   │
│ ├─ RouteETACalculator                                       │
│ ├─ FlightStateManager (get_flight_state_manager)            │
│                                                              │
│ Imports from app.core:                                      │
│ ├─ get_eta_calculator()                                     │
│                                                              │
│ Imports from app.models.flight_status:                      │
│ ├─ ETAMode, FlightPhase                                     │
│                                                              │
│ Imports from pathlib:                                       │
│ └─ Path                                                     │
│                                                              │
│ Endpoints:                                                  │
│ │                                                            │
│ └─ GET /api/pois/etas  ⚠️ LARGE & COMPLEX                   │
│    Function: get_pois_with_etas()                           │
│    Deps: route_manager, poi_manager                         │
│    Query Params:                                            │
│    ├─ route_id: Optional[str]                               │
│    ├─ latitude, longitude, speed_knots: Optional[str]       │
│    ├─ status_filter: Optional[str]  (comma-separated)       │
│    ├─ category: Optional[str]  (comma-separated)            │
│    └─ active_only: bool = True                              │
│    Returns: POIETAListResponse                              │
│    Logic Segments (365 lines):                              │
│    ├─ [40 lines] Telemetry extraction & routing             │
│    ├─ [40 lines] Parameter parsing & defaults               │
│    ├─ [15 lines] Route progress calculation                 │
│    ├─ [10 lines] Filter parsing (status, category)          │
│    ├─ [160 lines] POI loop:                                 │
│    │   ├─ calculate_distance()                              │
│    │   ├─ ETA calculation (dual-mode: est/anticipated)      │
│    │   ├─ calculate_bearing()                               │
│    │   ├─ calculate_course_status()                         │
│    │   ├─ Route-aware status determination                  │
│    │   ├─ Filter application                                │
│    │   ├─ Active status check                               │
│    │   └─ POIWithETA object construction                    │
│    ├─ [3 lines] Sort by ETA                                 │
│    └─ [1 line] Return response                              │
│                                                              │
│    Helper Function Calls:                                   │
│    ├─ calculate_bearing()  ×N (once per POI)                │
│    ├─ calculate_course_status()  ×N (once per POI)          │
│    └─ _calculate_poi_active_status()  ×N (once per POI)     │
│                                                              │
│    Service Calls:                                           │
│    ├─ _coordinator.get_current_telemetry()                  │
│    ├─ _coordinator.route_manager.get_active_route()         │
│    ├─ _coordinator.position_sim.progress (if available)     │
│    ├─ route_manager.get_active_route()                      │
│    ├─ RouteETACalculator.get_route_progress()               │
│    ├─ get_eta_calculator()                                  │
│    │  ├─ eta_calc.calculate_distance()  ×N                  │
│    │  ├─ eta_calc._calculate_route_aware_eta_*()  ×N        │
│    │  └─ eta_calc.calculate_eta()  ×N                       │
│    ├─ get_flight_state_manager().get_status()               │
│    └─ poi_manager.list_pois()                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### stats.py (Dependencies) ↓

```text
┌─────────────────────────────────────────────────────────────┐
│ stats.py - STATISTICS ENDPOINTS (230 lines)                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Imports from helpers.py:                                    │
│ ├─ extract_telemetry()  [NEW - EXTRACTED]                   │
│ ├─ get_flight_state_snapshot()  [NEW - EXTRACTED]           │
│ └─ find_closest_poi()  [NEW - EXTRACTED]                    │
│                                                              │
│ Imports from fastapi:                                       │
│ ├─ APIRouter                                                │
│ ├─ HTTPException, status                                    │
│ ├─ Query, Depends                                           │
│                                                              │
│ Imports from app.services:                                  │
│ ├─ POIManager (Depends)                                     │
│                                                              │
│ Imports from app.core:                                      │
│ └─ get_eta_calculator()                                     │
│                                                              │
│ Endpoints:                                                  │
│ │                                                            │
│ ├─ GET /api/pois/count/total                                │
│ │  Function: count_pois()  (~20 lines)                      │
│ │  Deps: poi_manager                                        │
│ │  Returns: {"count": int, "route_id": Optional[str]}       │
│ │  Uses: poi_manager.count_pois()                           │
│ │                                                            │
│ ├─ GET /api/pois/stats/next-destination                     │
│ │  Function: get_next_destination()  (~100 lines)           │
│ │  Deps: poi_manager                                        │
│ │  Query Params: latitude, longitude, speed_knots           │
│ │  Returns: {                                               │
│ │    "name": str,                                           │
│ │    "eta_type": str,                                       │
│ │    "flight_phase": Optional[str],                         │
│ │    "eta_seconds": float                                   │
│ │  }                                                        │
│ │  Uses: extract_telemetry()                                │
│ │        get_flight_state_snapshot()                        │
│ │        find_closest_poi()                                 │
│ │        poi_manager.list_pois()                            │
│ │        get_eta_calculator()                               │
│ │                                                            │
│ ├─ GET /api/pois/stats/next-eta                             │
│ │  Function: get_next_eta()  (~100 lines)                   │
│ │  Deps: poi_manager                                        │
│ │  Query Params: latitude, longitude, speed_knots           │
│ │  Returns: {                                               │
│ │    "eta_seconds": float,                                  │
│ │    "eta_type": str,                                       │
│ │    "flight_phase": Optional[str]                          │
│ │  }                                                        │
│ │  Uses: extract_telemetry()                                │
│ │        get_flight_state_snapshot()                        │
│ │        find_closest_poi()                                 │
│ │        poi_manager.list_pois()                            │
│ │        get_eta_calculator()                               │
│ │                                                            │
│ └─ GET /api/pois/stats/approaching                          │
│    Function: get_approaching_pois()  (~60 lines)            │
│    Deps: poi_manager                                        │
│    Query Params: latitude, longitude, speed_knots           │
│    Returns: {"count": int}                                  │
│    Threshold: 1800 seconds (30 minutes)                     │
│    Uses: extract_telemetry()                                │
│          poi_manager.list_pois()                            │
│          get_eta_calculator()                               │
│          eta_calc.calculate_distance()  ×N                  │
│          eta_calc.calculate_eta()  ×N                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### **init**.py (Dependencies) ↓

```text
┌─────────────────────────────────────────────────────────────┐
│ __init__.py - MODULE COMPOSITION (50 lines)                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Imports:                                                    │
│ ├─ fastapi.APIRouter                                        │
│ ├─ .crud import router as crud_router                       │
│ ├─ .etas import router as etas_router                       │
│ └─ .stats import router as stats_router                     │
│                                                              │
│ Module Contents:                                            │
│ │                                                            │
│ ├─ _coordinator: Optional[object] = None  (global state)    │
│ │                                                            │
│ ├─ set_coordinator(coordinator)  (module-level function)    │
│ │  Sets: global _coordinator                                │
│ │  Called by: app.main when initializing coordinator        │
│ │                                                            │
│ ├─ router = APIRouter(prefix="/api/pois", tags=["pois"])    │
│ │  Composed of:                                             │
│ │  ├─ router.include_router(crud_router)                    │
│ │  ├─ router.include_router(etas_router)                    │
│ │  └─ router.include_router(stats_router)                   │
│ │                                                            │
│ └─ __all__ = ["router", "set_coordinator"]                  │
│                                                              │
│ NOTE: _coordinator needs to be accessible to submodules:    │
│ ├─ Solution 1: Pass via function params (preferred)         │
│ ├─ Solution 2: Import from __init__ in submodules           │
│ └─ Current: Global reference (requires import in submodules)│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. CROSS-MODULE DEPENDENCY GRAPH

```text
┌──────────────────────────────────────────────────────────────────────┐
│ EXTERNAL SERVICES (not part of pois module)                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  POIManager                    RouteManager          ETA Calculator   │
│  (Depends injection)           (Depends injection)   (Singleton)      │
│       ↑                              ↑                    ↑            │
│       │                              │                    │            │
│       │                              │                    │            │
│   ┌───┴────────────────────────────────┴────────────────────┴──────┐  │
│   │                                                                 │  │
│   │                          crud.py                              │  │
│   │                      (220 lines)                              │  │
│   │  ┌──────────────────────────────────────────────────────┐    │  │
│   │  │ list_pois()                                          │    │  │
│   │  │ get_poi()                                            │    │  │
│   │  │ create_poi()              ←─────────────┐            │    │  │
│   │  │ update_poi()                           │             │    │  │
│   │  │ delete_poi()                           │             │    │  │
│   │  │ count_pois()                           │             │    │  │
│   │  └──────────────────────────────────────────────────────┘    │  │
│   │          │                                       ↑             │  │
│   │          │ calls                                 │             │  │
│   │          ↓                                       │             │  │
│   │  ┌──────────────────────────────────────────────┴───────┐    │  │
│   │  │ helpers.py                                           │    │  │
│   │  │ (150 lines - FOUNDATION)                             │    │  │
│   │  │ ┌─────────────────────────────────────────────────┐  │    │  │
│   │  │ │ _calculate_poi_active_status() ◄────┐           │  │    │  │
│   │  │ │ poi_to_response()                    │           │  │    │  │
│   │  │ │ extract_telemetry()              ┌───┴─────┐     │  │    │  │
│   │  │ │ get_flight_state_snapshot()      │         │     │  │    │  │
│   │  │ │ find_closest_poi()               │         │     │  │    │  │
│   │  │ │ calculate_bearing()              │         │     │  │    │  │
│   │  │ │ calculate_course_status()        │         │     │  │    │  │
│   │  │ └─────────────────────────────────────────────────┘  │    │  │
│   │  └──────────────────────────────────────────────────────┘    │  │
│   │          ↑                                                    │  │
│   │          │                                                    │  │
│   │    ┌─────┴──────────────────────────────────────────┐        │  │
│   │    │                                                │        │  │
│   │    │                  etas.py                       │        │  │
│   │    │             (280 lines - COMPLEX)             │        │  │
│   │    │  ┌───────────────────────────────────────────┐ │        │  │
│   │    │  │ get_pois_with_etas()                      │ │        │  │
│   │    │  │   ├─ calculate_bearing()                  │ │        │  │
│   │    │  │   ├─ calculate_course_status()            │ │        │  │
│   │    │  │   └─ _calculate_poi_active_status()       │ │        │  │
│   │    │  └───────────────────────────────────────────┘ │        │  │
│   │    └─────────────────────────────────────────────────┘        │  │
│   │          ↑                                                    │  │
│   │          │                                                    │  │
│   │    ┌─────┴──────────────────────────────────────────┐        │  │
│   │    │                                                │        │  │
│   │    │                  stats.py                      │        │  │
│   │    │             (230 lines)                        │        │  │
│   │    │  ┌───────────────────────────────────────────┐ │        │  │
│   │    │  │ count_pois()                              │ │        │  │
│   │    │  │ get_next_destination()  ←────┐            │ │        │  │
│   │    │  │   ├─ extract_telemetry()     │            │ │        │  │
│   │    │  │   ├─ get_flight_state_snap() │            │ │        │  │
│   │    │  │   └─ find_closest_poi()      │            │ │        │  │
│   │    │  │                              │            │ │        │  │
│   │    │  │ get_next_eta()               │            │ │        │  │
│   │    │  │   ├─ extract_telemetry()     │            │ │        │  │
│   │    │  │   ├─ get_flight_state_snap() │            │ │        │  │
│   │    │  │   └─ find_closest_poi()      │            │ │        │  │
│   │    │  │                              │            │ │        │  │
│   │    │  │ get_approaching_pois()       │            │ │        │  │
│   │    │  │   └─ extract_telemetry()     │            │ │        │  │
│   │    │  └───────────────────────────────────────────┘ │        │  │
│   │    └─────────────────────────────────────────────────┘        │  │
│   │          ↑                                                    │  │
│   │          │                                                    │  │
│   │    ┌─────┴──────────────────────────────────────────┐        │  │
│   │    │                                                │        │  │
│   │    │               __init__.py                      │        │  │
│   │    │           (50 lines - COMPOSITION)             │        │  │
│   │    │  ┌───────────────────────────────────────────┐ │        │  │
│   │    │  │ _coordinator: Optional[object]            │ │        │  │
│   │    │  │ set_coordinator()                         │ │        │  │
│   │    │  │ router (includes crud, etas, stats)       │ │        │  │
│   │    │  └───────────────────────────────────────────┘ │        │  │
│   │    └─────────────────────────────────────────────────┘        │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. DATA FLOW: GET /api/pois/etas (Complex Example)

```text
Client Request: GET /api/pois/etas?latitude=41.6&longitude=-74.0&speed_knots=67
    │
    ├─→ FastAPI Router (pois/__init__.py)
    │   └─→ get_pois_with_etas() (etas.py)
    │
    ├─→ [1] Extract Telemetry
    │   ├─ Check _coordinator availability
    │   ├─ If available: get_current_telemetry()
    │   └─ Else: use query parameters or defaults
    │
    ├─→ [2] Get Active Route
    │   ├─ RouteManager.get_active_route()  (from Depends)
    │   └─ Or: _coordinator.route_manager.get_active_route()
    │
    ├─→ [3] Calculate Route Progress
    │   ├─ If available from simulator: use directly
    │   └─ Else: RouteETACalculator.get_route_progress()
    │
    ├─→ [4] Parse Filters
    │   ├─ status_filter: split comma-separated string
    │   └─ category_filter: split comma-separated string
    │
    ├─→ [5] Get Flight State
    │   ├─ get_flight_state_manager().get_status()
    │   └─ Extract: eta_mode, flight_phase, is_pre_departure
    │
    ├─→ [6] Get All POIs
    │   └─ poi_manager.list_pois(route_id=route_id)
    │
    ├─→ [7] For Each POI:
    │   │
    │   ├─ [7a] Calculate Distance
    │   │   └─ ETACalculator.calculate_distance(lat, lon, poi.lat, poi.lon)
    │   │
    │   ├─ [7b] Calculate ETA
    │   │   ├─ If active_route + ESTIMATED mode:
    │   │   │   └─ ETACalculator._calculate_route_aware_eta_estimated()
    │   │   ├─ If active_route + ANTICIPATED mode:
    │   │   │   └─ ETACalculator._calculate_route_aware_eta_anticipated()
    │   │   └─ Fallback: ETACalculator.calculate_eta(distance, speed)
    │   │
    │   ├─ [7c] Calculate Bearing
    │   │   └─ calculate_bearing(lat, lon, poi.lat, poi.lon)  [helpers.py]
    │   │
    │   ├─ [7d] Calculate Course Status
    │   │   └─ calculate_course_status(heading, bearing)  [helpers.py]
    │   │
    │   ├─ [7e] Determine Route Status
    │   │   ├─ Check if on active route
    │   │   ├─ Calculate progress markers
    │   │   └─ Determine: ahead_on_route, already_passed, not_on_route
    │   │
    │   ├─ [7f] Check POI Active Status
    │   │   └─ _calculate_poi_active_status(poi, route_manager)  [helpers.py]
    │   │
    │   ├─ [7g] Apply Filters
    │   │   ├─ If status_filter set and not passing: skip
    │   │   ├─ If category_filter set and not passing: skip
    │   │   └─ If active_only=true and not active: skip
    │   │
    │   └─ [7h] Build POIWithETA Response
    │       └─ POIWithETA(poi_id, name, lat, lon, ..., eta_seconds, ...)
    │
    ├─→ [8] Sort Results
    │   └─ Sort by eta_seconds (ascending, inf for negative)
    │
    └─→ [9] Return POIETAListResponse
        └─ {"pois": [...], "total": count}
```

---

## 6. IMPORT STRATEGY & CIRCULAR DEPENDENCY PREVENTION

### Current Issue (Before Refactoring)

```text
pois.py (monolithic)
  ├─ Single file, no internal circular dependencies
  └─ ✓ No issues
```

### New Structure (After Refactoring)

```text
pois/__init__.py
  ├─ imports crud_router from .crud
  ├─ imports etas_router from .etas
  ├─ imports stats_router from .stats
  └─ defines _coordinator (global state)

pois/helpers.py
  ├─ NO imports from crud, etas, stats (pure utilities)
  └─ imports from external services only

pois/crud.py
  ├─ imports from .helpers (safe)
  └─ NO imports from etas, stats (safe)

pois/etas.py
  ├─ imports from .helpers (safe)
  └─ NO imports from crud, stats (safe)

pois/stats.py
  ├─ imports from .helpers (safe)
  └─ NO imports from crud, etas (safe)
```

### \_coordinator Global State Management

```text
Problem: _coordinator is global state that needs to be shared
Solution: Define in __init__.py, import in other modules

Option 1: Import from __init__ (RECOMMENDED)
  │
  ├─ helpers.py:
  │   from . import _coordinator  # or access via function param
  │
  ├─ crud.py:
  │   from . import _coordinator
  │
  ├─ etas.py:
  │   from . import _coordinator
  │
  └─ stats.py:
      from . import _coordinator

Option 2: Pass as function parameter (BETTER)
  └─ Avoid global state by passing _coordinator as param
     But this changes function signatures significantly

RECOMMENDED: Keep global in __init__.py, import where needed
  ├─ Minimal refactoring
  ├─ Maintains existing API
  └─ Clear single source of truth
```

---

## 7. MODULE SIZE ESTIMATES

```text
Current Structure:
┌───────────────────┬────────┬──────────────┐
│ File              │ Lines  │ % of Total   │
├───────────────────┼────────┼──────────────┤
│ pois.py           │ 1159   │ 100%         │
│                   │        │              │
│ Global/Config     │ 37     │ 3%           │
│ Math Helpers      │ 56     │ 5%           │
│ Status Helpers    │ 56     │ 5%           │
│                   │        │              │
│ CRUD Endpoints    │ 450    │ 39%          │
│ ETA Endpoint      │ 365    │ 32%  ⚠️      │
│ Stats Endpoints   │ 245    │ 21%          │
│ Mixed             │ 100    │ 9%  ⚠️       │
└───────────────────┴────────┴──────────────┘

New Structure:
┌─────────────────────────────────────┬────────┬──────────────┐
│ File                                │ Lines  │ % of Total   │
├─────────────────────────────────────┼────────┼──────────────┤
│ __init__.py                         │ 50     │ 5%           │
│ helpers.py                          │ 150    │ 16%          │
│ crud.py                             │ 220    │ 24%  ✓       │
│ etas.py                             │ 280    │ 30%  ✓       │
│ stats.py                            │ 230    │ 25%  ✓       │
│                                     │        │              │
│ TOTAL                               │ 930    │ 100% ✓       │
│ Reduction                           │ -229   │ -20%         │
└─────────────────────────────────────┴────────┴──────────────┘

Benefits:
 ✓ All files < 300 lines
 ✓ 20% reduction in total lines (eliminated duplication)
 ✓ Clear separation of concerns
 ✓ Each module has single responsibility
```
