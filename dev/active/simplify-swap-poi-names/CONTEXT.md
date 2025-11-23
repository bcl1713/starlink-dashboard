# Context for simplify-swap-poi-names

**Branch:** `feat/simplify-swap-poi-names`
**Folder:** `dev/active/simplify-swap-poi-names/`
**Last Updated:** 2025-11-22

---

## Background

Satellite swap POIs currently display detailed satellite transition information (e.g., "X-Band\nX-1→X-2", "CommKa\nAOR→POR") which is non-actionable for mission operators. Operators need to know that a swap event is occurring, but the specific satellite identifiers add visual clutter without providing operational value. This work simplifies the naming to reduce information overload in map displays and exported documents while maintaining the distinction between swap types (X-Band vs CommKa) and gap event types (Entry vs Exit).

**Motivation:** Satellite names aren't actionable information for operators.

**Why now:** User feedback indicated the current labels are too verbose.

---

## Relevant Code Locations

Primary file to modify:

- `backend/starlink-location/app/mission/timeline_service.py` — contains POI naming functions (lines 1399-1426)
  - `_format_commka_exit_entry()` (lines 1399-1402) — formats gap exit/entry POIs
  - `_format_commka_transition_label()` (lines 1404-1413) — formats CommKa swap POIs
  - `_format_x_transition_label()` (lines 1415-1426) — formats X-Band swap POIs

Code that calls these functions:

- `backend/starlink-location/app/mission/timeline_service.py`
  - `_sync_ka_pois()` (lines 1102-1193) — generates CommKa POIs
  - `_sync_x_aar_pois()` (lines 1195-1241) — generates X-Band POIs

Files that consume POI names (no changes needed, just verification):

- `backend/starlink-location/app/mission/exporter.py` — exports POIs to CSV, XLSX, PDF, PPTX
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` — displays POIs on map

---

## Dependencies

- **Backend service:** starlink-location (Python/FastAPI)
- **Docker Compose:** Must rebuild with `--no-cache` after Python code changes
- **Grafana:** Displays POI labels on map panels
- **Prometheus:** Stores POI metadata as metrics
- **Database:** SQLite stores POI entries (schema unchanged, only name field values change)

**No external API dependencies.**

**No environment variable changes required.**

---

## Constraints & Assumptions

- **Constraint:** AAR POI naming must remain unchanged ("AAR\nStart" / "AAR\nEnd")
- **Constraint:** CommKa gap events must distinguish Exit vs Entry (no satellite names)
- **Constraint:** No migration of existing POIs (forward-only change)
- **Assumption:** Existing unit tests do not hard-code expected POI names with satellite details
- **Assumption:** The `\n` newline character in POI names is correctly handled by Grafana and export functions

---

## Risks

- **Risk:** Existing unit tests may expect specific POI name formats and could fail
  - **Impact:** Test failures would block deployment
  - **Mitigation:** Run full test suite during verification phase, update test assertions if needed
- **Risk:** Grafana map labels may not render `\n` correctly, causing display issues
  - **Impact:** POI labels could appear as "X-Band Swap" (space) instead of two lines
  - **Mitigation:** Manual verification in Grafana during verification phase
- **Risk:** Users may be confused by loss of satellite identification in POIs
  - **Impact:** Support questions or requests to revert
  - **Mitigation:** Scope already confirmed with user that satellite names are non-actionable

---

## Testing Strategy

Define exactly what "done and verified" means:

### Automated Tests

- Run backend test suite: `pytest backend/starlink-location/tests/` (or equivalent)
- All existing tests must pass (update test assertions if they check POI names)

### Manual Verification Steps

1. **Rebuild Docker environment:**
   ```bash
   docker compose down && docker compose build --no-cache && docker compose up -d
   ```

2. **Verify backend health:**
   ```bash
   curl http://localhost:8000/health
   ```
   Expected: `{"status":"ok",...}`

3. **Create or activate a test mission with route and timing data:**
   - Use existing sample routes in `/data/sample_routes/`
   - Activate route and trigger mission-event POI generation

4. **Check POI names via API:**
   ```bash
   curl http://localhost:8000/api/pois | jq '.[] | select(.category=="mission-event") | .name'
   ```
   Expected output includes:
   - `"X-Band\nSwap"`
   - `"CommKa\nSwap"`
   - `"CommKa\nExit"`
   - `"CommKa\nEntry"`
   - `"AAR\nStart"` (unchanged)
   - `"AAR\nEnd"` (unchanged)

5. **Verify Grafana map display:**
   - Open http://localhost:3000/d/starlink/fullscreen-overview
   - Confirm POI labels show simplified names on map markers

6. **Verify exported documents:**
   - Export mission to CSV, XLSX, PDF, PPTX
   - Confirm POI names in exported files match simplified format

---

## References

- Initial exploration findings documented in session chat
- Related POI functionality: Route management (see CLAUDE.md)
- Mission event categories defined in timeline_service.py lines 34-50
