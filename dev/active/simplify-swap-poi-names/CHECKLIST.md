# Checklist for simplify-swap-poi-names

**Branch:** `feat/simplify-swap-poi-names`
**Folder:** `dev/active/simplify-swap-poi-names/`
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
    * feat/simplify-swap-poi-names
    ```
  - [x] If you are on a different branch, switch with:
    ```bash
    git checkout feat/simplify-swap-poi-names
    ```

---

## Implementation Tasks

### Task 1: Modify CommKa Exit/Entry POI Naming Function

- [ ] Open the file:
  ```bash
  /home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/mission/timeline_service.py
  ```

- [ ] Locate the function `_format_commka_exit_entry()` around line 1399

- [ ] **Current code:**
  ```python
  def _format_commka_exit_entry(kind: str, satellite: str | None) -> str:
      label = satellite or "Unknown"
      return f"CommKa\n{kind} {label}"
  ```

- [ ] **Replace with:**
  ```python
  def _format_commka_exit_entry(kind: str, satellite: str | None) -> str:
      # Simplified: no satellite name, just Exit or Entry
      return f"CommKa\n{kind}"
  ```

- [ ] Save the file

- [ ] **Expected result:** The function now returns "CommKa\nExit" or "CommKa\nEntry" without satellite names

- [ ] Commit this change:
  ```bash
  git add backend/starlink-location/app/mission/timeline_service.py
  git commit -m "feat: simplify CommKa exit/entry POI names (remove satellite)"
  ```

- [ ] Push to remote:
  ```bash
  git push -u origin feat/simplify-swap-poi-names
  ```

---

### Task 2: Modify CommKa Transition/Swap POI Naming Function

- [ ] In the same file (`timeline_service.py`), locate the function `_format_commka_transition_label()` around line 1404

- [ ] **Current code:**
  ```python
  def _format_commka_transition_label(
      from_satellite: str | None, to_satellite: str | None
  ) -> str:
      if from_satellite and to_satellite:
          return f"CommKa\n{from_satellite}→{to_satellite}"
      if to_satellite:
          return f"CommKa\n→{to_satellite}"
      return "CommKa\nTransition"
  ```

- [ ] **Replace with:**
  ```python
  def _format_commka_transition_label(
      from_satellite: str | None, to_satellite: str | None
  ) -> str:
      # Simplified: all CommKa swaps show as "CommKa\nSwap"
      return "CommKa\nSwap"
  ```

- [ ] Save the file

- [ ] **Expected result:** The function now always returns "CommKa\nSwap" regardless of satellite parameters

- [ ] Commit this change:
  ```bash
  git add backend/starlink-location/app/mission/timeline_service.py
  git commit -m "feat: simplify CommKa swap POI names (remove satellite details)"
  ```

- [ ] Push to remote:
  ```bash
  git push
  ```

---

### Task 3: Modify X-Band Transition POI Naming Function

- [ ] In the same file (`timeline_service.py`), locate the function `_format_x_transition_label()` around line 1415

- [ ] **Current code:**
  ```python
  def _format_x_transition_label(
      current_satellite: str | None,
      target_satellite: str | None,
      is_same_satellite: bool,
  ) -> str:
      if is_same_satellite:
          return "X-Band\nBeam Swap"
      if current_satellite and target_satellite:
          return f"X-Band\n{current_satellite}→{target_satellite}"
      if target_satellite:
          return f"X-Band\n→{target_satellite}"
      return "X-Band\nTransition"
  ```

- [ ] **Replace with:**
  ```python
  def _format_x_transition_label(
      current_satellite: str | None,
      target_satellite: str | None,
      is_same_satellite: bool,
  ) -> str:
      # Simplified: all X-Band swaps show as "X-Band\nSwap"
      return "X-Band\nSwap"
  ```

- [ ] Save the file

- [ ] **Expected result:** The function now always returns "X-Band\nSwap" regardless of parameters

- [ ] Commit this change:
  ```bash
  git add backend/starlink-location/app/mission/timeline_service.py
  git commit -m "feat: simplify X-Band swap POI names (remove satellite details)"
  ```

- [ ] Push to remote:
  ```bash
  git push
  ```

---

## Verification Tasks

### Task 4: Rebuild Docker Environment

- [ ] Stop all containers:
  ```bash
  docker compose down
  ```

- [ ] **Expected result:** Output shows containers stopping and network being removed

- [ ] Rebuild with no cache (CRITICAL for Python changes):
  ```bash
  docker compose build --no-cache
  ```

- [ ] **Expected result:** Build process runs for several minutes, rebuilding all layers

- [ ] Start services:
  ```bash
  docker compose up -d
  ```

- [ ] **Expected result:** All services start in detached mode

- [ ] Wait for services to become healthy (30-60 seconds), then check status:
  ```bash
  docker compose ps
  ```

- [ ] **Expected result:** All containers show "healthy" status

---

### Task 5: Verify Backend Health

- [ ] Check backend health endpoint:
  ```bash
  curl http://localhost:8000/health
  ```

- [ ] **Expected result:** JSON response with `"status":"ok"`

- [ ] Check API documentation is accessible:
  ```bash
  curl -I http://localhost:8000/docs
  ```

- [ ] **Expected result:** HTTP 200 response

---

### Task 6: Test POI Name Generation via API

- [ ] Query all mission-event POIs:
  ```bash
  curl -s http://localhost:8000/api/pois | jq '.[] | select(.category=="mission-event") | {name: .name, category: .category}'
  ```

- [ ] **Expected result:** POI names should include:
  - `"X-Band\nSwap"` (not "X-Band\nX-1→X-2" or similar)
  - `"CommKa\nSwap"` (not "CommKa\nAOR→POR" or similar)
  - `"CommKa\nExit"` (not "CommKa\nExit AOR" or similar)
  - `"CommKa\nEntry"` (not "CommKa\nEnter POR" or similar)
  - `"AAR\nStart"` (unchanged)
  - `"AAR\nEnd"` (unchanged)

- [ ] If no mission-event POIs exist, create a test mission:
  - [ ] Upload or activate a route via UI: http://localhost:8000/ui/routes
  - [ ] Ensure route has timing data and triggers mission analysis
  - [ ] Re-run the POI query above

---

### Task 7: Verify Grafana Map Display

- [ ] Open Grafana in browser:
  ```
  http://localhost:3000
  ```

- [ ] Login (default: admin / admin)

- [ ] Navigate to Fullscreen Overview dashboard:
  ```
  http://localhost:3000/d/starlink/fullscreen-overview
  ```

- [ ] Locate the map panel showing POI markers

- [ ] **Expected result:** POI labels on map show:
  - "X-Band
    Swap" (two lines)
  - "CommKa
    Swap" (two lines)
  - "CommKa
    Exit" (two lines)
  - "CommKa
    Entry" (two lines)

- [ ] Confirm no satellite names appear in these POI labels

---

### Task 8: Verify Exported Documents (CSV)

- [ ] Export a mission to CSV via API (replace `{mission_id}` with actual ID):
  ```bash
  curl -o /tmp/mission_export.csv http://localhost:8000/api/missions/{mission_id}/export/csv
  ```

- [ ] Open the CSV file:
  ```bash
  cat /tmp/mission_export.csv | grep -E "(X-Band|CommKa|AAR)"
  ```

- [ ] **Expected result:** POI names in CSV should show simplified format:
  - "X-Band\nSwap" (may appear as "X-Band Swap" in CSV rendering)
  - "CommKa\nSwap"
  - "CommKa\nExit"
  - "CommKa\nEntry"

---

### Task 9: Verify Exported Documents (XLSX, PDF, PPTX)

- [ ] Export mission to XLSX:
  ```bash
  curl -o /tmp/mission_export.xlsx http://localhost:8000/api/missions/{mission_id}/export/xlsx
  ```

- [ ] Export mission to PDF:
  ```bash
  curl -o /tmp/mission_export.pdf http://localhost:8000/api/missions/{mission_id}/export/pdf
  ```

- [ ] Export mission to PPTX:
  ```bash
  curl -o /tmp/mission_export.pptx http://localhost:8000/api/missions/{mission_id}/export/pptx
  ```

- [ ] **Manual inspection required:** Open each exported file and confirm POI names match simplified format

- [ ] **Expected result:** All export formats show simplified POI names without satellite details

---

### Task 10: Run Automated Tests

- [ ] Run backend test suite (if available):
  ```bash
  docker exec starlink-location pytest /app/tests/ -v
  ```

- [ ] **Expected result:** All tests pass (or tests updated if they hard-coded POI name assertions)

- [ ] If tests fail due to POI name assertions:
  - [ ] Update test files to expect new POI name format
  - [ ] Re-run tests until passing
  - [ ] Commit test updates:
    ```bash
    git add backend/starlink-location/tests/
    git commit -m "test: update POI name assertions for simplified format"
    git push
    ```

---

## Documentation Maintenance

- [ ] Update PLAN.md status:
  - [ ] Open `dev/active/simplify-swap-poi-names/PLAN.md`
  - [ ] Change `**Status:** Planning` to `**Status:** Completed`
  - [ ] Save the file
  - [ ] Commit:
    ```bash
    git add dev/active/simplify-swap-poi-names/PLAN.md
    git commit -m "docs: mark plan as completed"
    git push
    ```

- [ ] Review CONTEXT.md:
  - [ ] Open `dev/active/simplify-swap-poi-names/CONTEXT.md`
  - [ ] Add any discovered constraints, risks, or testing notes
  - [ ] If changes made, commit:
    ```bash
    git add dev/active/simplify-swap-poi-names/CONTEXT.md
    git commit -m "docs: update context with verification findings"
    git push
    ```

- [ ] Update LESSONS-LEARNED.md (if applicable):
  - [ ] If anything surprising or notable occurred during implementation, document it
  - [ ] Open `dev/LESSONS-LEARNED.md`
  - [ ] Add entry with date, feature slug, and lesson
  - [ ] Commit if updated

---

## Pre-Wrap Checklist

All of the following must be checked before handoff to `wrapping-up-plan`:

- [ ] All implementation tasks above are marked `- [x]`
- [ ] All verification tasks above are marked `- [x]`
- [ ] Docker containers rebuilt with `--no-cache` successfully
- [ ] Backend health endpoint returns OK
- [ ] POI names verified via `/api/pois` endpoint
- [ ] Grafana map displays simplified POI labels
- [ ] Exported documents (CSV, XLSX, PDF, PPTX) contain simplified names
- [ ] All automated tests pass
- [ ] No TODOs remain in modified code
- [ ] PLAN.md status updated to "Completed"
- [ ] CONTEXT.md reviewed and updated if needed
- [ ] LESSONS-LEARNED.md updated if applicable
- [ ] All changes committed and pushed to `feat/simplify-swap-poi-names` branch
