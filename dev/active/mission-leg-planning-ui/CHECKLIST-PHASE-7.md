# Checklist: Phase 7 - Testing & Documentation

**Branch:** `feat/mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
**Phase:** 7 - Testing & Documentation
**Status:** Not Started

> This checklist covers writing comprehensive tests for backend and frontend, and updating project documentation with new workflows and examples.

---

## Phase 7 Overview

**Goal:** Write comprehensive tests for backend and frontend. Update project documentation with new workflows and examples.

**Exit Criteria:**
- Backend unit tests cover new models and endpoints (>80% coverage)
- Frontend component tests written
- E2E test covers full mission creation → export → import workflow
- CLAUDE.md updated with mission planning guide
- API documentation complete in OpenAPI spec
- User guide created with screenshots

---

## 7.1: Backend Unit Tests

### 7.1.1: Test Mission and MissionLeg models

- [x] Open or create `backend/starlink-location/tests/test_mission_models.py`
- [x] Add tests for MissionLeg model:
  ```python
  def test_mission_leg_creation():
      """Test creating a MissionLeg instance."""
      leg = MissionLeg(
          id="leg-1",
          name="Test Leg",
          route_id="route-1",
          description="Test description"
      )
      assert leg.id == "leg-1"
      assert leg.name == "Test Leg"
      assert leg.route_id == "route-1"
  ```
- [x] Add tests for Mission model:
  ```python
  def test_mission_creation():
      """Test creating a Mission with legs."""
      mission = Mission(
          id="mission-1",
          name="Test Mission",
          description="Test",
          legs=[]
      )
      assert mission.id == "mission-1"
      assert len(mission.legs) == 0
  ```
- [x] Add tests for nested legs:
  ```python
  def test_mission_with_legs():
      """Test Mission with multiple legs."""
      leg1 = MissionLeg(id="leg-1", name="Leg 1")
      leg2 = MissionLeg(id="leg-2", name="Leg 2")
      mission = Mission(
          id="mission-1",
          name="Test",
          legs=[leg1, leg2]
      )
      assert len(mission.legs) == 2
  ```
- [x] Run tests:
  ```bash
  source backend/starlink-location/venv/bin/activate && pytest backend/starlink-location/tests/test_mission_models.py -v
  ```
- [x] Expected: All model tests pass

### 7.1.2: Test hierarchical storage functions

- [ ] Open or create `backend/starlink-location/tests/test_mission_storage.py`
- [ ] Add tests for save_mission_v2:
  ```python
  def test_save_mission_v2(tmp_path):
      """Test saving hierarchical mission."""
      # Use tmp_path for isolated testing
      # Test mission saved to correct structure
      # Test legs saved separately
  ```
- [ ] Add tests for load_mission_v2:
  ```python
  def test_load_mission_v2(tmp_path):
      """Test loading hierarchical mission."""
      # Create test mission files
      # Load and verify structure
  ```
- [ ] Run tests:
  ```bash
  source backend/starlink-location/venv/bin/activate && pytest backend/starlink-location/tests/test_mission_storage.py -v
  ```
- [ ] Expected: All storage tests pass

### 7.1.3: Test v2 API endpoints

- [ ] Open or create `backend/starlink-location/tests/test_routes_v2.py`
- [ ] Add test for POST /api/v2/missions
- [ ] Add test for GET /api/v2/missions
- [ ] Add test for GET /api/v2/missions/{id}
- [ ] Add test for DELETE /api/v2/missions/{id}
- [ ] Add test for export endpoint
- [ ] Run tests:
  ```bash
  source backend/starlink-location/venv/bin/activate && pytest backend/starlink-location/tests/test_routes_v2.py -v
  ```
- [ ] Expected: All API tests pass

### 7.1.4: Test export package generation

- [ ] Open or create `backend/starlink-location/tests/test_package_exporter.py`
- [ ] Add test for export_mission_package function
- [ ] Verify zip structure
- [ ] Verify manifest.json contents
- [ ] Run tests:
  ```bash
  source backend/starlink-location/venv/bin/activate && pytest backend/starlink-location/tests/test_package_exporter.py -v
  ```
- [ ] Expected: Export tests pass

---

## 7.2: Frontend Unit Tests

### 7.2.1: Configure Vitest

- [ ] Verify `frontend/mission-planner/vite.config.ts` has test configuration:
  ```typescript
  import { defineConfig } from 'vite';
  import react from '@vitejs/plugin-react';

  export default defineConfig({
    plugins: [react()],
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
    },
  });
  ```
- [ ] Create `frontend/mission-planner/src/test/setup.ts`:
  ```typescript
  import '@testing-library/jest-dom';
  ```
- [ ] Expected: Vitest configured for React testing

### 7.2.2: Test utility functions

- [ ] Create `frontend/mission-planner/src/lib/utils.test.ts`
- [ ] Add tests for any utility functions (date formatting, validation, etc.)
- [ ] Run tests:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run test
  ```
- [ ] Expected: Utility tests pass

### 7.2.3: Test API service functions

- [ ] Create `frontend/mission-planner/src/services/missions.test.ts`
- [ ] Mock axios responses
- [ ] Test missionsApi.list()
- [ ] Test missionsApi.get()
- [ ] Test missionsApi.create()
- [ ] Test missionsApi.delete()
- [ ] Run tests
- [ ] Expected: API service tests pass

### 7.2.4: Test React Query hooks

- [ ] Create `frontend/mission-planner/src/hooks/api/useMissions.test.ts`
- [ ] Use @testing-library/react-hooks or similar
- [ ] Test useMissions hook
- [ ] Test useCreateMission hook
- [ ] Test useDeleteMission hook
- [ ] Run tests
- [ ] Expected: Hook tests pass

---

## 7.3: Frontend Component Tests

### 7.3.1: Test MissionCard component

- [ ] Create `frontend/mission-planner/src/components/missions/MissionCard.test.tsx`
- [ ] Test rendering with mission data
- [ ] Test click handlers (onSelect, onDelete)
- [ ] Test leg count display
- [ ] Run tests
- [ ] Expected: MissionCard tests pass

### 7.3.2: Test MissionList component

- [ ] Create `frontend/mission-planner/src/components/missions/MissionList.test.tsx`
- [ ] Test loading state
- [ ] Test error state
- [ ] Test empty state
- [ ] Test rendering missions
- [ ] Run tests
- [ ] Expected: MissionList tests pass

### 7.3.3: Test CreateMissionDialog component

- [ ] Create `frontend/mission-planner/src/components/missions/CreateMissionDialog.test.tsx`
- [ ] Test form submission
- [ ] Test validation
- [ ] Test dialog open/close
- [ ] Run tests
- [ ] Expected: CreateMissionDialog tests pass

### 7.3.4: Test satellite configuration components

- [ ] Create tests for XBandConfig component
- [ ] Create tests for KaOutageConfig component
- [ ] Create tests for KuOutageConfig component
- [ ] Run tests
- [ ] Expected: Satellite config tests pass

---

## 7.4: End-to-End Tests

### 7.4.1: Configure Playwright

- [ ] Verify Playwright is installed:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner list @playwright/test
  ```
- [ ] Create `frontend/mission-planner/playwright.config.ts`:
  ```typescript
  import { defineConfig, devices } from '@playwright/test';

  export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',
    use: {
      baseURL: 'http://localhost:5173',
      trace: 'on-first-retry',
    },
    projects: [
      {
        name: 'chromium',
        use: { ...devices['Desktop Chrome'] },
      },
    ],
    webServer: {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
    },
  });
  ```
- [ ] Create `frontend/mission-planner/e2e/` directory
- [ ] Expected: Playwright configured

### 7.4.2: Write mission creation E2E test

- [ ] Create `frontend/mission-planner/e2e/mission-workflow.spec.ts`
- [ ] Implement test steps:
  ```typescript
  import { test, expect } from '@playwright/test';

  test('complete mission workflow', async ({ page }) => {
    // 1. Navigate to missions page
    await page.goto('/missions');

    // 2. Click "Create New Mission"
    await page.click('text=Create New Mission');

    // 3. Fill in mission details
    await page.fill('input[name="name"]', 'Test Mission E2E');
    await page.fill('input[name="description"]', 'E2E test mission');

    // 4. Submit form
    await page.click('button:has-text("Create Mission")');

    // 5. Verify mission appears in list
    await expect(page.locator('text=Test Mission E2E')).toBeVisible();

    // 6. Click mission to open detail
    await page.click('text=Test Mission E2E');

    // 7. Add a leg (if UI supports)
    // ... (detailed steps)

    // 8. Export mission
    await page.click('button:has-text("Export")');

    // 9. Wait for download
    const download = await page.waitForEvent('download');

    // 10. Verify export completed
    expect(download.suggestedFilename()).toMatch(/\.zip$/);
  });
  ```
- [ ] Run test:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run test:e2e
  ```
- [ ] Expected: E2E test passes

### 7.4.3: Write export/import E2E test

- [ ] Create test for full export → import workflow
- [ ] Test deleting mission
- [ ] Test importing zip file
- [ ] Verify mission recreated
- [ ] Run tests
- [ ] Expected: Export/import E2E test passes

---

## 7.5: Update CLAUDE.md

### 7.5.1: Add mission planning guide section

- [ ] Open `CLAUDE.md` at repo root
- [ ] Add new section "Mission Planning UI" after "Route Management":
  ```markdown
  ## Mission Planning UI

  ### Overview

  The mission planning UI allows you to create and manage multi-leg missions through a web interface. Access it at http://localhost:5173/missions.

  ### Creating a Mission

  1. Navigate to http://localhost:5173/missions
  2. Click "Create New Mission"
  3. Enter mission name and description
  4. Click "Create Mission"

  ### Adding Legs to a Mission

  1. Open a mission from the list
  2. Click "Add Leg"
  3. Configure leg details:
     - Upload KML route
     - Add POIs
     - Configure satellite transitions (X-Band, Ka, Ku)
     - Define AAR segments

  ### Satellite Configuration

  #### X-Band Transitions

  - Select starting satellite
  - Add transitions at waypoints
  - Specify from/to satellites

  #### Ka Outages

  - Define outage windows by waypoint range
  - Specify reason for outage

  #### Ku/Starlink Outages

  - Similar to Ka outages
  - Define start/end waypoints

  ### AAR Segments

  - Specify AAR start/end waypoints
  - Add altitude and notes

  ### Exporting Missions

  1. Click "Export" on mission card
  2. Wait for package generation
  3. Download zip file containing:
     - Mission metadata
     - All legs with configurations
     - Routes (KML files)
     - POIs
     - Pre-generated documents (PDF, XLSX, PPTX, CSV)

  ### Importing Missions

  1. Click "Import Mission"
  2. Drag and drop mission zip file
  3. Wait for validation
  4. Mission recreated with all assets
  ```
- [ ] Save file
- [ ] Expected: CLAUDE.md updated with mission planning guide

---

## 7.6: Update API Documentation

### 7.6.1: Verify OpenAPI docs

- [ ] Start backend:
  ```bash
  docker compose up -d
  ```
- [ ] Open http://localhost:8000/docs
- [ ] Verify all v2 endpoints are documented
- [ ] Verify request/response schemas are complete
- [ ] Add descriptions to any missing endpoints
- [ ] Expected: OpenAPI docs complete and accurate

---

## 7.7: Create User Guide (Optional)

### 7.7.1: Take screenshots

- [ ] Take screenshot of mission list page
- [ ] Take screenshot of mission creation dialog
- [ ] Take screenshot of leg detail page with satellite config
- [ ] Take screenshot of export dialog
- [ ] Take screenshot of import dialog
- [ ] Save screenshots to `docs/screenshots/mission-planner/`
- [ ] Expected: Screenshots captured

### 7.7.2: Write user guide

- [ ] Create `docs/mission-planner-user-guide.md`
- [ ] Add sections:
  - Overview
  - Getting Started
  - Creating Missions
  - Configuring Legs
  - Satellite Configuration
  - AAR Segments
  - Export/Import
  - Troubleshooting
- [ ] Embed screenshots
- [ ] Save file
- [ ] Expected: User guide complete

---

## 7.8: Run All Tests

### 7.8.1: Run backend test suite

- [ ] Run all backend tests:
  ```bash
  source backend/starlink-location/venv/bin/activate && pytest backend/starlink-location/tests/ -v --cov=app --cov-report=term-missing
  ```
- [ ] Verify >80% coverage
- [ ] Fix any failing tests
- [ ] Expected: All backend tests pass with good coverage

### 7.8.2: Run frontend unit tests

- [ ] Run all frontend unit tests:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run test
  ```
- [ ] Fix any failing tests
- [ ] Expected: All frontend unit tests pass

### 7.8.3: Run E2E tests

- [ ] Run Playwright E2E tests:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner run test:e2e
  ```
- [ ] Fix any failing tests
- [ ] Expected: All E2E tests pass

---

## 7.9: Commit Phase 7 Changes

- [ ] Stage all changes:
  ```bash
  git add backend/starlink-location/tests/
  git add frontend/mission-planner/src/
  git add frontend/mission-planner/e2e/
  git add CLAUDE.md
  git add docs/
  ```
- [ ] Commit:
  ```bash
  git commit -m "feat: add comprehensive testing and documentation

  - Add backend unit tests for models, storage, API
  - Add frontend unit tests for components and hooks
  - Add E2E tests for mission workflow
  - Update CLAUDE.md with mission planning guide
  - Verify OpenAPI documentation complete
  - Add user guide with screenshots

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 7"
  ```
- [ ] Push:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```
- [ ] Expected: Phase 7 committed and pushed

---

## Status

- [ ] All Phase 7 tasks completed
- [ ] Backend tests >80% coverage
- [ ] Frontend tests comprehensive
- [ ] E2E tests cover critical paths
- [ ] Documentation updated and complete
