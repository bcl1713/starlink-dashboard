# POI Import Sync Fix Plan

## Goal
Ensure POIs created during `import_pois` uploads are immediately visible across the API/UI by eliminating stale in-memory caches.

## Context
- `routes.py` instantiates its own `POIManager` and writes imported placemarks through that instance.
- `pois.py` (and other modules) hold a separate `POIManager` instance created at import time, so they continue serving an out-of-date snapshot.
- Integration test `test_upload_route_with_poi_import` expects `/api/pois` to reflect the upload, but this only holds when both modules share the same manager or reload the datastore before reads.

## Constraints
- Keep existing JSON storage contract (`/data/pois.json`) untouched.
- Avoid race conditions with the file lock (`filelock.FileLock`); reusing a singleton should preserve locking semantics.
- Maintain compatibility with tests that monkey-patch `POIManager` via `conftest.py`.

## Proposed Fix
1. **Unify POIManager lifecycle**
   - Initialize a single `POIManager` instance in `main.py` startup.
   - Inject that instance into `app.api.routes`, `app.api.pois`, `app.api.geojson`, metrics exporters, and ETA service initialization.
   - Remove module-level instantiations to prevent accidental divergence.
2. **Reload-on-demand fallback**
   - As a safety net, ensure read endpoints can trigger `reload_pois()` if they detect stale state (e.g., optional `force_reload` helper). The singleton should make this optional, but retain ability for manual refresh.
3. **Update tests & fixtures**
   - Adjust `tests/conftest.py` monkey patches to provide the pre-created singleton.
   - Re-run (or simulate) `test_upload_route_with_poi_import` to confirm `/api/pois` shows imported placemarks.
4. **Manual regression**
   - Upload KML with `import_pois` enabled via UI; verify success toast reflects counts, `/api/routes/{id}` and `/api/pois?route_id=...` agree, and UI list shows new POIs without full reload.
   - Smoke-test POI CRUD to confirm shared manager doesn’t break edits/deletes.

## Risks & Mitigations
- **Risk:** Late imports might still see stale data if other processes modify `pois.json`.  
  **Mitigation:** Document `reload_pois()` utility and expose admin endpoint if needed in future.
- **Risk:** Singleton introduces unexpected test coupling.  
  **Mitigation:** Ensure fixtures reset or replace the global manager per test (already done via monkey patch; update as part of step 3).

## Definition of Done
- Uploading a route with `import_pois=true` results in `imported_poi_count > 0` and those POIs appearing instantly at `/api/pois`.
- Integration test passes without additional sleeps/retries.
- Manual UI run shows per-route POI counts updating after upload.

