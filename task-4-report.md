# Task 4 report: v1 mission runtime/API retirement

## Delivered

- Removed the v1 `app.mission.routes` package and its `/api/missions` router registration.
- Removed v1 flat mission/checksum CRUD and flat timeline fallback, migration, and deletion from mission storage.
- Made all timeline storage APIs require `parent_mission_id` and retain only scoped v2 paths.
- Removed v1 global-state test reset and v1-only route tests.
- Added regression coverage that v1 endpoints return 404, v2 remains available, and `legacy.json`, `legacy.sha256`, and `legacy-leg.timeline.json` remain byte-identical through v2 listing, startup, and activation.
- Updated the active-context fixture to create a legacy flat artifact directly rather than importing a retired v1 storage helper.

## TDD evidence

RED observed:

```text
2 failed: /api/missions returned 200; /api/missions/example/activate returned 405
2 failed: scoped timeline read loaded/migrated legacy flat artifact; parent ID was optional
```

GREEN/verification:

```text
47 passed: active-context, router retirement, storage, scenario, and v2 route suites
975 passed, 22 skipped: complete backend test suite
black --check --diff app tests: passed (235 files unchanged)
```

## Audit

The v1 import/runtime audit found no production v1 route or flat-storage consumer. Remaining `/api/missions` entries are explicit 404 assertions; `routes_v2` and its `list_missions` function are v2 identifiers.

## Formatter note

`ruff check app tests` exits nonzero on 53 pre-existing import-order violations outside this task's changed behavior. Changed retirement files pass targeted Ruff validation.

## Correction: retained V2 storage regression coverage

- Restored V2-only regression cases for persisted timestamp ordering, metadata leg stubs, invalid metadata JSON, overwrite behavior, stale-leg pruning, and timeline-file exclusion from both full and metadata loads.
- The pruning regression additionally asserts that a scoped timeline is not mistaken for a leg JSON file or deleted while stale leg data is pruned.
- No V1 runtime, route, flat-storage, migration, or fallback behavior was restored.

### Correction TDD evidence

RED observed:

```text
pytest tests/unit/test_mission_storage.py::test_v2_metadata_listing_orders_persisted_timestamps -q
ERROR: not found ... (no match in any of [<Module test_mission_storage.py>])
```

GREEN/verification:

```text
11 passed: tests/unit/test_mission_storage.py
979 passed, 22 skipped: complete backend test suite
git diff --check: passed
```
