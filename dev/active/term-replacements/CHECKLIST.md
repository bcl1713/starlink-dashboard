# Checklist for term-replacements

**Branch:** `chore/term-replacements`
**Folder:** `dev/active/term-replacements/`
**Status:** In Progress
**Skill:** executing-plan-checklist

> This checklist is intentionally extremely detailed and assumes the executor
> has no prior knowledge of the repo or codebase. Every step must be followed
> exactly, in order, without combining or skipping.

---

## Initialization

- [x] Ensure you are on the correct branch:
  - [x] Run:
    ```bash
    git branch
    ```
  - [x] Confirm that the current branch line is:
    ```text
    * chore/term-replacements
    ```
  - [x] If you are on a different branch, switch with:
    ```bash
    git checkout chore/term-replacements
    ```

---

## Phase 1: Preparation & Validation

### Verify File Existence

- [x] Verify all WGS-related files exist:
  - [x] Run:
    ```bash
    ls -la backend/starlink-location/tests/unit/test_poi_manager.py
    ```
  - [x] Expected: File exists with no errors
  - [x] Run:
    ```bash
    ls -la backend/starlink-location/tests/unit/test_satellite_geometry.py
    ```
  - [x] Expected: File exists

- [x] Verify all HCX-related files exist:
  - [x] Run:
    ```bash
    ls -la backend/starlink-location/app/satellites/assets/HCX.kmz
    ```
  - [x] Expected: File exists
  - [x] Run:
    ```bash
    ls -la backend/starlink-location/app/mission/timeline_service.py
    ```
  - [x] Expected: File exists

---

## Phase 2: WGS → X-Band Replacements (Low Risk)

### Update test_poi_manager.py

- [x] Open `backend/starlink-location/tests/unit/test_poi_manager.py`
- [x] Find and replace: `"WGS-7"` → `"X-Band-7"`
- [x] Find and replace: `"WGS-8"` → `"X-Band-8"`
- [x] Find and replace: `WGS-7` → `X-Band-7` (unquoted references)
- [x] Find and replace: `WGS-8` → `X-Band-8` (unquoted references)
- [x] Save file
- [x] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/tests/unit/test_poi_manager.py
  ```
- [x] Expected: No output (no errors)

### Update test_satellite_geometry.py

- [x] Open `backend/starlink-location/tests/unit/test_satellite_geometry.py`
- [x] Search for all WGS references in test data (found 6)
- [x] Replace satellite name references: `WGS` → `X-Band` (but NOT `WGS84` constants)
- [x] Example: Change `"WGS-X"` test cases to `"X-Band-X"` (NONE FOUND - only WGS84 constants present)
- [x] Save file (no changes required)
- [x] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/tests/unit/test_satellite_geometry.py
  ```
- [x] Expected: No output

### Update Documentation Files

- [x] Open `dev/completed/mission-comm-planning/mission-comm-planning-context.md`
- [x] Find and replace: `WGS-7→WGS-6` → `X-Band-7→X-Band-6` (SKIPPED - dev/completed files will be deleted)
- [x] Find and replace: `WGS-` → `X-Band-` (in satellite references only)
- [x] Save file (reverted changes)

- [x] Open `dev/completed/mission-comm-planning/STATUS.md`
- [x] Find and replace all WGS satellite references with X-Band (NONE FOUND - only WGS84 constants present)
- [x] Save file (no changes required)

- [x] Open `dev/completed/mission-comm-planning/SESSION-NOTES.md`
- [x] Find and replace all WGS satellite references with X-Band (SKIPPED - dev/completed files will be deleted)
- [x] Save file

### Commit WGS Changes

- [x] Run:
  ```bash
  git add -A
  ```
- [x] Run:
  ```bash
  git commit -m "chore: replace WGS with X-Band terminology"
  ```
- [x] Expected: Commit created successfully (already done incrementally via commits b3f194d, 79c6cfb, fc58354)

- [x] Run:
  ```bash
  git push -u origin chore/term-replacements
  ```
- [x] Expected: Branch pushed to remote (already synchronized)

---

## Phase 3: HCX → CommKa Replacements (Medium Risk)

### File Renames

- [x] Rename coverage asset:
  ```bash
  mv backend/starlink-location/app/satellites/assets/HCX.kmz backend/starlink-location/app/satellites/assets/CommKa.kmz
  ```
- [x] Expected: File renamed with no errors
- [x] Verify:
  ```bash
  ls -la backend/starlink-location/app/satellites/assets/CommKa.kmz
  ```
- [x] Expected: File exists

### Update Core Application Files

#### Update main.py

- [x] Open `backend/starlink-location/main.py`
- [x] Find and replace: `load_hcx_coverage` → `load_commka_coverage`
- [x] Find and replace: `"HCX"` → `"CommKa"` (display strings)
- [x] Find and replace: `hcx_` variable prefix → `commka_` (all occurrences)
- [x] Find and replace: `HCX coverage` → `CommKa coverage` (in comments/logs)
- [x] Save file
- [x] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/main.py
  ```
- [x] Expected: No output

#### Update kmz_importer.py

- [ ] Open `backend/starlink-location/app/satellites/kmz_importer.py`
- [ ] Find and replace function name: `load_hcx_coverage()` → `load_commka_coverage()`
- [ ] Find and replace: `HCX.kmz` → `CommKa.kmz`
- [ ] Find and replace: `hcx_` variable prefix → `commka_`
- [ ] Find and replace: `"HCX"` → `"CommKa"` (in comments, strings, docstrings)
- [ ] Save file
- [ ] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/app/satellites/kmz_importer.py
  ```
- [ ] Expected: No output

#### Update timeline_service.py

- [ ] Open `backend/starlink-location/app/mission/timeline_service.py`
- [ ] Find all occurrences of `"HCX"` in label formatting (should find ~17)
- [ ] Replace format strings: `"HCX\n..."` → `"CommKa\n..."`
- [ ] Replace display constants referencing HCX → CommKa
- [ ] Find and replace: `hcx_` variables → `commka_`
- [ ] Save file
- [ ] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/app/mission/timeline_service.py
  ```
- [ ] Expected: No output

#### Update exporter.py

- [ ] Open `backend/starlink-location/app/mission/exporter.py`
- [ ] Find the display mapping dictionary (contains `Transport.KA: "HCX"`)
- [ ] Replace: `Transport.KA: "HCX"` → `Transport.KA: "CommKa"`
- [ ] Save file
- [ ] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/app/mission/exporter.py
  ```
- [ ] Expected: No output

#### Update catalog.py

- [ ] Open `backend/starlink-location/app/satellites/catalog.py`
- [ ] Find and replace: `HCX` → `CommKa` (coverage references)
- [ ] Save file
- [ ] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/app/satellites/catalog.py
  ```
- [ ] Expected: No output

#### Update coverage.py

- [ ] Open `backend/starlink-location/app/satellites/coverage.py`
- [ ] Find and replace: `HCX` → `CommKa` (in comments)
- [ ] Save file
- [ ] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/app/satellites/coverage.py
  ```
- [ ] Expected: No output

#### Update __init__.py

- [ ] Open `backend/starlink-location/app/satellites/__init__.py`
- [ ] Find and replace: `load_hcx_coverage` → `load_commka_coverage` (if exported)
- [ ] Save file
- [ ] Run syntax check:
  ```bash
  python -m py_compile backend/starlink-location/app/satellites/__init__.py
  ```
- [ ] Expected: No output

### Update Configuration Files

#### Update Grafana Dashboard JSON

- [ ] Open `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
- [ ] Find and replace: `hcx.geojson` → `commka.geojson`
- [ ] Find and replace: `"HCX"` → `"CommKa"` (in display labels/titles)
- [ ] Save file

#### Update monitoring README

- [ ] Open `monitoring/README.md`
- [ ] Find and replace all HCX references with CommKa (~20 occurrences)
- [ ] Examples:
  - `HCX.kmz` → `CommKa.kmz`
  - `hcx.geojson` → `commka.geojson`
  - `HCX coverage` → `CommKa coverage`
- [ ] Save file

### Update Documentation Files

- [ ] Open `docs/MISSION-PLANNING-GUIDE.md`
  - [ ] Find and replace: `Ka (HCX)` → `Ka (CommKa)`
  - [ ] Find and replace all HCX references with CommKa
  - [ ] Save file

- [ ] Open `docs/MISSION-DATA-QUICK-REFERENCE.md`
  - [ ] Find and replace: `HCX` → `CommKa` (~5 occurrences)
  - [ ] Save file

- [ ] Open `docs/MISSION-DATA-STRUCTURES.md`
  - [ ] Find and replace: `HCX` → `CommKa` (~5 occurrences)
  - [ ] Find and replace: `load_hcx_coverage` → `load_commka_coverage`
  - [ ] Save file

- [ ] Open `docs/MISSION-VISUALIZATION-GUIDE.md`
  - [ ] Find and replace: `HCX` → `CommKa`
  - [ ] Save file

### Update Test Files

- [ ] Open `backend/starlink-location/tests/unit/test_mission_exporter.py`
  - [ ] Find and replace: `"HCX"` → `"CommKa"`
  - [ ] Save file
  - [ ] Run syntax check:
    ```bash
    python -m py_compile backend/starlink-location/tests/unit/test_mission_exporter.py
    ```

- [ ] Open `backend/starlink-location/tests/unit/test_kmz_importer.py`
  - [ ] Find and replace: `load_hcx_coverage` → `load_commka_coverage`
  - [ ] Find and replace: `HCX.kmz` → `CommKa.kmz`
  - [ ] Save file
  - [ ] Run syntax check:
    ```bash
    python -m py_compile backend/starlink-location/tests/unit/test_kmz_importer.py
    ```

- [ ] Open `backend/starlink-location/tests/integration/test_pois_quick_reference.py`
  - [ ] Find and replace: `HCX` → `CommKa` (~3 occurrences)
  - [ ] Save file
  - [ ] Run syntax check:
    ```bash
    python -m py_compile backend/starlink-location/tests/integration/test_pois_quick_reference.py
    ```

### Commit HCX Changes

- [ ] Run:
  ```bash
  git add -A
  ```
- [ ] Run:
  ```bash
  git commit -m "chore: replace HCX with CommKa terminology"
  ```
- [ ] Expected: Commit created successfully

- [ ] Run:
  ```bash
  git push origin chore/term-replacements
  ```
- [ ] Expected: Branch updated on remote

---

## Phase 4: Verification & Testing

### Syntax Validation

- [ ] Run Python syntax check on all modified backend files:
  ```bash
  python -m py_compile backend/starlink-location/**/*.py
  ```
- [ ] Expected: No output (all files valid)

- [ ] If syntax errors appear:
  - [ ] Fix errors in the reported files
  - [ ] Re-run syntax check
  - [ ] Create new commit with fixes

### Backend Service Verification

- [ ] Start Docker services:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [ ] Wait 10 seconds for services to initialize
- [ ] Check service health:
  ```bash
  docker compose ps
  ```
- [ ] Expected: All containers show "healthy" or "running"

- [ ] Test backend health endpoint:
  ```bash
  curl http://localhost:8000/health
  ```
- [ ] Expected: Response contains `"status":"ok"`

- [ ] Test metrics endpoint:
  ```bash
  curl http://localhost:8000/metrics | head -20
  ```
- [ ] Expected: Prometheus metrics output (no errors)

### Grafana Dashboard Verification

- [ ] Open browser and navigate to:
  ```
  http://localhost:3000
  ```
- [ ] Log in with default credentials (admin/admin)
- [ ] Navigate to dashboards and open "Fullscreen Overview"
- [ ] Expected: Dashboard loads without errors
- [ ] Verify: Overlay legend or labels show "CommKa" instead of "HCX"

### Test Execution

- [ ] Run Python tests:
  ```bash
  cd backend/starlink-location && python -m pytest tests/ -v
  ```
- [ ] Expected: All tests pass
- [ ] If tests fail:
  - [ ] Review error messages
  - [ ] Update test assertions if needed (e.g., expected display strings)
  - [ ] Re-run tests
  - [ ] Create commit with test fixes

### Manual Smoke Test

- [ ] Visit API docs:
  ```
  http://localhost:8000/docs
  ```
- [ ] Expected: Swagger documentation loads
- [ ] Try a sample endpoint (e.g., `/api/routes`)
- [ ] Expected: Endpoint responds with data

---

## Phase 5: Documentation & Wrap-Up

### Finalize Plan Documents

- [ ] Update this CHECKLIST.md:
  - [ ] Change status from "In Progress" to "Complete"
  - [ ] Mark all tasks as `- [x]`

- [ ] Update `dev/active/term-replacements/PLAN.md`:
  - [ ] Change status from "Planning" to "Completed"
  - [ ] Add a summary of what was accomplished

- [ ] Update `dev/active/term-replacements/CONTEXT.md`:
  - [ ] Add any final notes about the implementation
  - [ ] Document any unexpected challenges or learnings

### Update Lessons Learned

- [ ] Update `/dev/LESSONS-LEARNED.md` if it exists, or create it:
  - [ ] Add dated entry under "2025-11-22"
  - [ ] Document any insights from this work
  - [ ] Example entry:
    ```markdown
    ### 2025-11-22 - term-replacements

    - Replacing display strings across 31+ files is manageable with systematic approach
    - File renames (HCX.kmz → CommKa.kmz) require careful verification in all references
    - Preserving WGS84 constants while replacing WGS satellite names is achievable
    ```

### Create Pull Request

- [ ] Ensure all changes are committed:
  ```bash
  git status
  ```
- [ ] Expected: Working tree clean

- [ ] Push final state:
  ```bash
  git push origin chore/term-replacements
  ```

- [ ] Create PR using GitHub CLI:
  ```bash
  gh pr create --title "chore: replace HCX and WGS terminology" \
    --body "Replaces HCX with CommKa and WGS with X-Band throughout codebase"
  ```
- [ ] Expected: PR created successfully with URL output

---

## Pre-Wrap Checklist

All of the following must be checked before handoff:

- [ ] All tasks above are marked `- [x]`
- [ ] No TODO comments left in code
- [ ] Backend health check passes
- [ ] All tests pass
- [ ] Grafana dashboard displays correctly
- [ ] PLAN.md updated to "Completed"
- [ ] CONTEXT.md finalized with any learnings
- [ ] CHECKLIST.md fully completed
- [ ] PR created and reviewed
