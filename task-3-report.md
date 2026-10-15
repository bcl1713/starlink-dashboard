# Task 3 Fix Evidence — Overview cross-leg POI isolation

## Scope

Fixed the Task 3 review blocker in `backend/starlink-location/app/api/overview_upcoming_pois.py` only. Overview now admits a trusted generated timeline POI returned for the resolved parent only when its `route_id` is absent or equals the resolved active leg route ID. The existing `list_pois(mission_id=parent_mission_id)` query remains the parent-mission boundary.

No POI list/ETA resolver lifecycle changes were made: this correction needs only the already-resolved Overview context and does not add per-POI resolution.

## Regression coverage

Added `test_api_excludes_generated_pois_from_an_inactive_leg_of_the_same_parent` in `tests/integration/test_overview_upcoming_pois_api.py`.

The test persists one parent with an active and inactive leg on distinct routes, supplies trusted generated records for both routes, and verifies that Overview returns only the active-leg record. It also verifies that a matching-parent generated record without `route_id` remains visible.

### Route-less record ruling

Route-less matching-parent generated POIs are retained. `POI.route_id` is explicitly optional (`str | None`), and the existing active-status policy in `app/api/pois/helpers.py` treats mission-bound records as active when `route_id is None or route_id == resolution.context.route_id`. Timeline generation currently writes a route ID, but the model and established consumer behavior permit route-less records, so excluding them in Overview would be a compatibility regression.

## Test evidence

- RED before implementation:
  `uv run --python .venv/bin/python pytest tests/integration/test_overview_upcoming_pois_api.py::test_api_excludes_generated_pois_from_an_inactive_leg_of_the_same_parent -q`
  failed with unexpected `inactive-leg-poi` in the response.
- GREEN after implementation: same regression test passed.
- Focused verification:
  `uv run --python .venv/bin/python pytest tests/integration/test_overview_upcoming_pois_api.py tests/unit/test_overview_upcoming_pois.py tests/unit/test_poi_manager.py -q`
  → `51 passed` (one third-party Starlette/AnyIO deprecation warning).
- Full backend suite:
  `uv run --python .venv/bin/python pytest tests -q`
  → `1068 passed, 22 skipped` (four existing third-party warnings).
- `git diff --check` passed.
