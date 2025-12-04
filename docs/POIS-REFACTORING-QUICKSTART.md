# POIs Refactoring - Quick Start Guide

This document provides a quick reference for the pois.py refactoring task.

## Problem Statement

The `app/api/pois.py` file has grown to 1159 lines and violates the project's
target of <300 lines per module. The file mixes multiple concerns (CRUD, ETA
calculations, statistics) and contains ~160 lines of duplicated code.

## Solution Overview

Split into 5 modular components:

- `pois/__init__.py` - 50 lines (router composition)
- `pois/helpers.py` - 150 lines (utilities)
- `pois/crud.py` - 220 lines (CRUD endpoints)
- `pois/etas.py` - 280 lines (ETA endpoint)
- `pois/stats.py` - 230 lines (statistics endpoints)

**Result:** 930 lines total (-20% reduction, +clarity)

---

## Quick Reference Table

### Endpoints Distribution

| Module       | Endpoints                                                                | Count |
| ------------ | ------------------------------------------------------------------------ | ----- |
| **crud.py**  | GET /, GET /{id}, POST /, PUT /{id}, DELETE /{id}, GET /count/total      | 6     |
| **etas.py**  | GET /etas                                                                | 1     |
| **stats.py** | GET /stats/next-destination, GET /stats/next-eta, GET /stats/approaching | 3     |

### Functions & Line Numbers (Current File)

| Function                         | Lines     | Type     | Issue                        |
| -------------------------------- | --------- | -------- | ---------------------------- |
| `set_coordinator()`              | 30-33     | Setup    | Move to **init**.py          |
| `calculate_bearing()`            | 40-65     | Helper   | Move to helpers.py           |
| `calculate_course_status()`      | 68-95     | Helper   | Move to helpers.py           |
| `_calculate_poi_active_status()` | 98-153    | Helper   | Move to helpers.py           |
| `list_pois()`                    | 156-256   | Endpoint | Move to crud.py              |
| `get_pois_with_etas()`           | 259-624   | Endpoint | Move to etas.py (365 lines!) |
| `count_pois()`                   | 627-648   | Endpoint | Move to stats.py or crud.py  |
| `get_next_destination()`         | 651-751   | Endpoint | Move to stats.py             |
| `get_next_eta()`                 | 754-854   | Endpoint | Move to stats.py             |
| `get_approaching_pois()`         | 857-919   | Endpoint | Move to stats.py             |
| `get_poi()`                      | 922-976   | Endpoint | Move to crud.py              |
| `create_poi()`                   | 979-1054  | Endpoint | Move to crud.py              |
| `update_poi()`                   | 1057-1129 | Endpoint | Move to crud.py              |
| `delete_poi()`                   | 1132-1159 | Endpoint | Move to crud.py              |

### Duplicated Code to Extract

| Pattern                   | Occurrences | Lines   | Extract to                            |
| ------------------------- | ----------- | ------- | ------------------------------------- |
| Telemetry extraction      | 3x          | 60      | `helpers.extract_telemetry()`         |
| Flight state snapshot     | 4x          | 32      | `helpers.get_flight_state_snapshot()` |
| POI response construction | 5x          | 90      | `helpers.poi_to_response()`           |
| Find closest POI          | 2x          | 18      | `helpers.find_closest_poi()`          |
| **TOTAL**                 | -           | **200** | **7 new functions**                   |

---

## Module Dependencies

### Dependency Graph (NO circular dependencies!)

```text
helpers.py (FOUNDATION)
    ↑
    ├─ crud.py (imports helpers)
    ├─ etas.py (imports helpers)
    └─ stats.py (imports helpers)

__init__.py (COMPOSITION)
    └─ includes: crud_router, etas_router, stats_router
```

### Critical Functions Used Across Modules

- `_calculate_poi_active_status()` - used by: crud, etas
- `calculate_bearing()` - used by: etas
- `calculate_course_status()` - used by: etas
- `extract_telemetry()` - used by: stats
- `get_flight_state_snapshot()` - used by: stats
- `find_closest_poi()` - used by: stats
- `poi_to_response()` - used by: crud

---

## Implementation Order

### Phase 1: Foundation (helpers.py)

1. Create `app/api/pois/` directory
2. Create `helpers.py` with all 7 functions
3. Move existing math helpers
4. Add new extracted functions

### Phase 2: CRUD Module

1. Create `crud.py`
2. Move endpoints: list_pois, get_poi, create_poi, update_poi, delete_poi,
   count_pois
3. Import helpers: `_calculate_poi_active_status()`, `poi_to_response()`
4. Test CRUD operations

### Phase 3: ETA Module

1. Create `etas.py`
2. Move `get_pois_with_etas()`
3. Import helpers: `calculate_bearing()`, `calculate_course_status()`,
   `_calculate_poi_active_status()`
4. Test ETA endpoint

### Phase 4: Stats Module

1. Create `stats.py`
2. Move endpoints: count_pois, get_next_destination, get_next_eta,
   get_approaching_pois
3. Import helpers: `extract_telemetry()`, `get_flight_state_snapshot()`,
   `find_closest_poi()`
4. Test stats endpoints

### Phase 5: Integration

1. Create `__init__.py` with router composition
2. Add `set_coordinator()` function
3. Update imports in `app/main.py`
4. Remove old `pois.py`
5. Run full test suite

---

## Files to Create/Modify

### Create (5 files):

```text
backend/starlink-location/app/api/pois/
├── __init__.py              ← new
├── helpers.py               ← new
├── crud.py                  ← new
├── etas.py                  ← new
└── stats.py                 ← new
```

### Modify (2 files):

```text
app/main.py
  from app.api.pois import router, set_coordinator

app/api/__init__.py
  (update imports if needed)
```

### Delete (1 file):

```text
app/api/pois.py (after migration complete)
```

---

## Key Metrics

| Metric           | Before    | After   | Change   |
| ---------------- | --------- | ------- | -------- |
| Total Lines      | 1159      | 930     | -20%     |
| Max File Size    | 1159      | 280     | -76%     |
| Duplication      | 160 lines | 0 lines | -100%    |
| Modules          | 1         | 5       | +4       |
| Endpoints        | 10        | 10      | 0 (same) |
| Helper Functions | 4         | 7       | +3       |

---

## Testing Checklist

After migration, verify:

- [ ] All 10 endpoints still work correctly
- [ ] GET /api/pois returns POI list
- [ ] GET /api/pois/etas calculates ETA data
- [ ] GET /api/pois/stats/\* endpoints return statistics
- [ ] POST/PUT/DELETE operations work
- [ ] Error handling is consistent
- [ ] set_coordinator() is accessible from app.main
- [ ] No import errors
- [ ] Existing tests pass
- [ ] New modular structure follows project patterns (like routes/)

---

## Related Documentation

- Full Analysis: `docs/pois_refactoring_analysis.md`
- Dependency Diagrams: `docs/pois_dependency_diagrams.md`
- Executive Summary: `docs/REFACTORING_SUMMARY.txt`

---

## Questions?

Refer to the detailed documents:

1. `REFACTORING_SUMMARY.txt` for overview and issues
2. `pois_refactoring_analysis.md` for complete function list and grouping
3. `pois_dependency_diagrams.md` for visual dependency trees and data flow
