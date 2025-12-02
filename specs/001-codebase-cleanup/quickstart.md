# Quickstart Guide: Codebase Refactoring Workflow

**Feature**: 001-codebase-cleanup
**Created**: 2025-12-02
**Version**: 1.0
**Purpose**: Practical, step-by-step guide for executing constitutional refactoring

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Workflow Overview](#2-workflow-overview)
3. [Step-by-Step Process](#3-step-by-step-process)
4. [Example Walkthrough](#4-example-walkthrough)
5. [Common Patterns](#5-common-patterns)
6. [Troubleshooting](#6-troubleshooting)
7. [Command Reference](#7-command-reference)

---

## 1. Prerequisites

### Required Tools

```bash
# Verify these are installed before starting
python --version      # Python 3.12+
node --version        # Node 20+
docker --version      # Docker 24+
git --version         # Git 2.40+

# Install Python linting tools
pip install black ruff pytest

# Install frontend tools
cd frontend/mission-planner
npm install
cd ../..

# Install pre-commit (optional but recommended)
pip install pre-commit
```

### Environment Setup

1. **Clone and verify repository state**:

   ```bash
   cd /home/brian/Projects/starlink-dashboard-dev
   git status
   git branch
   ```

2. **Ensure Docker environment works**:

   ```bash
   docker compose up -d
   docker compose ps  # All containers should be healthy
   curl http://localhost:8000/health
   docker compose down
   ```

3. **Set up refactoring branch**:

   ```bash
   git checkout main
   git pull origin main
   git checkout -b 001-codebase-cleanup
   ```

### Required Reading

- [spec.md](./spec.md) - Feature requirements and success criteria
- [research.md](./research.md) - Refactoring strategies and best practices
- [data-model.md](./data-model.md) - Entity definitions and state machines
- [contracts/smoke-test-checklist.md](./contracts/smoke-test-checklist.md) - Testing procedures

---

## 2. Workflow Overview

```
┌────────────────────────────────────────────────────────────────┐
│                    REFACTORING WORKFLOW                        │
└────────────────────────────────────────────────────────────────┘

1. SELECT TARGET FILE
   ├─ Review violation list (spec.md "Known Violations")
   ├─ Start with P0 critical (>1000 lines, backend API/service)
   └─ Check for dependencies (avoid files with circular refs)
        ↓
2. ASSESS & PLAN
   ├─ Read file, understand structure
   ├─ Identify logical boundaries (routes, services, helpers)
   ├─ Plan split strategy (see research.md Section 1 or 2)
   └─ Document plan in task notes
        ↓
3. CREATE FEATURE BRANCH & PR (DRAFT)
   ├─ Branch: refactor/[scope]-[filename]
   ├─ Create draft PR immediately (enables CI feedback)
   └─ Add PR description with smoke test checklist
        ↓
4. REFACTOR CODE
   ├─ Split file into logical modules (<300 lines each)
   ├─ Extract shared logic to service layer
   ├─ Maintain backward compatibility (re-export in __init__.py)
   └─ Commit frequently with descriptive messages
        ↓
5. RUN LINTERS (LOCAL)
   ├─ Black/ruff (Python) or Prettier/ESLint (TS/JS)
   ├─ Fix all violations (no suppression comments)
   └─ Commit formatting fixes separately
        ↓
6. REBUILD & SMOKE TEST
   ├─ Docker rebuild: down → build --no-cache → up -d
   ├─ Execute smoke tests from contracts/smoke-test-checklist.md
   ├─ Document results in PR description
   └─ Fix any failures, repeat until all pass
        ↓
7. FINALIZE PR
   ├─ Mark PR ready for review
   ├─ Verify CI passes (linters, type checks)
   ├─ Request review from team/self-review
   └─ Address feedback if any
        ↓
8. MERGE & TRACK
   ├─ Squash merge to 001-codebase-cleanup
   ├─ Update tracking files (code-files.json, tasks.json)
   └─ Delete feature branch

REPEAT for next file until 80% compliance reached
```

---

## 3. Step-by-Step Process

### Step 1: Select Target File

**Goal**: Choose the next file to refactor based on priority and feasibility.

**Procedure**:

1. **Review violation list** in [spec.md](./spec.md#known-violations-pre-refactoring-assessment):

   ```bash
   # Backend critical violations (start here)
   backend/starlink-location/app/api/ui.py             # 3995 lines - HIGHEST PRIORITY
   backend/starlink-location/app/mission/exporter.py   # 1927 lines
   backend/starlink-location/app/api/routes.py         # 1046 lines
   backend/starlink-location/app/api/pois.py           # 1092 lines

   # Moderate violations (after critical)
   backend/starlink-location/app/core/metrics.py       # 850 lines
   frontend/mission-planner/src/components/common/RouteMap.tsx  # 482 lines
   ```

2. **Check dependencies** (avoid circular references):

   ```bash
   # Find imports in target file
   rg "^from app\." backend/starlink-location/app/api/routes.py
   rg "^import " backend/starlink-location/app/api/routes.py

   # Find files that import target file
   rg "from app.api.routes import" backend/starlink-location/app/
   ```

3. **Select file** with:
   - Highest priority (P0 critical > P1 high > P2 medium)
   - No circular dependencies
   - Clear logical boundaries

**Output**: Target file path documented in task notes.

---

### Step 2: Assess & Plan

**Goal**: Understand file structure and plan refactoring strategy.

**Procedure**:

1. **Read file** and identify structure:

   ```bash
   # Count lines and review structure
   wc -l backend/starlink-location/app/api/routes.py

   # List function/class definitions
   rg "^def |^class |^async def " backend/starlink-location/app/api/routes.py

   # Count route endpoints (FastAPI example)
   rg "@router\.(get|post|put|delete)" backend/starlink-location/app/api/routes.py | wc -l
   ```

2. **Identify logical boundaries**:

   For FastAPI route files, group by:
   - **CRUD operations**: List, Get, Create, Update, Delete
   - **Functional domains**: Route management, uploads, statistics, timing, cache

   For React components, split by:
   - **Custom hooks**: Data fetching, action handlers, form state
   - **Sub-components**: Header, body, footer, modals
   - **Utilities**: Formatting, validation, calculations

   For services, extract:
   - **Helper functions**: Pure calculations, formatters
   - **External dependencies**: API clients, file I/O
   - **Core logic**: Business rules, state management

3. **Plan split strategy** (refer to [research.md](./research.md)):

   **Example for routes.py (1046 lines)**:
   ```
   Target Structure:
   app/api/routes/
   ├── __init__.py           # Re-export all routers (backward compatibility)
   ├── management.py         # List, get, activate, deactivate (200-250 lines)
   ├── upload.py             # Upload, download, delete (150-200 lines)
   ├── stats.py              # Stats, progress, ETA calculations (200-250 lines)
   ├── timing.py             # Route timing profile endpoints (150 lines)
   └── cache.py              # ETA cache management (100 lines)

   Service Layer (if needed):
   app/services/
   ├── route_stats.py        # Extract shared statistics logic
   └── route_validator.py    # Extract validation logic
   ```

4. **Document plan** in task notes:

   ```bash
   # Create task tracking file (optional but recommended)
   mkdir -p specs/001-codebase-cleanup/tracking
   cat > specs/001-codebase-cleanup/tracking/task-routes-py.md <<EOF
   # Task: Refactor app/api/routes.py

   **File**: backend/starlink-location/app/api/routes.py
   **Current Lines**: 1046
   **Target**: 5 files @ <300 lines each
   **Estimated Effort**: Large (8-12 hours)

   ## Split Plan
   1. management.py - route listing, activation, deactivation
   2. upload.py - KML upload, download, delete
   3. stats.py - progress, ETA calculations
   4. timing.py - timing profile CRUD
   5. cache.py - ETA cache management

   ## Dependencies
   - app.services.route_manager (existing)
   - app.services.kml_parser (existing)
   - NEW: app.services.route_stats (extract shared logic)

   ## Backward Compatibility
   - __init__.py re-exports all routers
   - main.py includes composite router: app.include_router(routes.router)
   EOF
   ```

**Output**: Written plan with target structure, file boundaries, dependencies.

---

### Step 3: Create Feature Branch & PR (Draft)

**Goal**: Set up version control and CI feedback loop.

**Procedure**:

1. **Create feature branch**:

   ```bash
   git checkout 001-codebase-cleanup
   git pull origin 001-codebase-cleanup  # Sync with remote

   # Branch naming: refactor/[scope]-[filename-without-ext]
   git checkout -b refactor/api-routes-py
   ```

2. **Create draft PR immediately** (enables early CI feedback):

   ```bash
   # Push empty branch to create PR
   git push -u origin refactor/api-routes-py

   # Create PR using GitHub CLI (or web UI)
   gh pr create --draft \
     --title "refactor(api): split routes.py into focused modules" \
     --body "$(cat <<EOF
   ## Summary

   Refactors \`app/api/routes.py\` (1046 lines) into 5 focused modules
   (<300 lines each) to achieve FR-001 compliance.

   **Addresses**: FR-001, FR-005, FR-018, SC-001
   **Target Structure**:
   - \`app/api/routes/management.py\` - Route CRUD operations
   - \`app/api/routes/upload.py\` - File upload/download
   - \`app/api/routes/stats.py\` - Statistics and progress
   - \`app/api/routes/timing.py\` - Timing profiles
   - \`app/api/routes/cache.py\` - ETA cache management

   ## Changes

   - [ ] Create module structure under \`app/api/routes/\`
   - [ ] Split endpoints into focused routers
   - [ ] Extract shared logic to service layer
   - [ ] Maintain backward compatibility via \`__init__.py\`
   - [ ] Update main.py imports
   - [ ] Run linters (Black, ruff)
   - [ ] Smoke test all endpoints

   ## Smoke Test Checklist

   **Test Category**: Backend API
   **Environment**: Docker (simulation mode)

   ### Tests to Perform (from contracts/smoke-test-checklist.md)

   - [ ] 2.3 Routes API Tests - PENDING
     - [ ] List all routes (GET /api/routes)
     - [ ] Get route by ID (GET /api/routes/{id})
     - [ ] Upload KML file (POST /api/routes/upload)
     - [ ] Activate route (POST /api/routes/{id}/activate)
     - [ ] Deactivate routes (POST /api/routes/deactivate)
     - [ ] Delete route (DELETE /api/routes/{id})
     - [ ] Get route statistics (GET /api/routes/{id}/stats)

   ### Smoke Test Results

   _Results will be documented here after testing_

   ## Testing

   - [ ] All existing integration tests pass
   - [ ] Manual smoke tests completed
   - [ ] No behavior changes detected

   ## Checklist

   - [ ] Code formatted (Black, ruff pass)
   - [ ] Type hints on all functions
   - [ ] Docstrings on all functions
   - [ ] No circular dependencies
   - [ ] All files <300 lines
   EOF
   )"
   ```

**Output**: Draft PR created with checklist and test plan.

---

### Step 4: Refactor Code

**Goal**: Split file into logical modules while preserving behavior.

**Procedure**:

1. **Create target directory structure**:

   ```bash
   mkdir -p backend/starlink-location/app/api/routes
   ```

2. **Extract first logical group** (e.g., management endpoints):

   ```bash
   # Create new file
   cat > backend/starlink-location/app/api/routes/management.py <<'EOF'
   """
   Route management endpoints.

   Handles listing, retrieval, activation, and deactivation of flight routes.
   """
   from fastapi import APIRouter, HTTPException, Depends
   from typing import List, Optional

   from app.models.route import RouteResponse, RouteListResponse
   from app.services.route_manager import get_route_manager, RouteManager

   router = APIRouter(tags=["routes"])


   @router.get("/", response_model=RouteListResponse)
   async def list_routes(
       route_manager: RouteManager = Depends(get_route_manager)
   ) -> RouteListResponse:
       """
       List all available routes.

       Returns both uploaded KML routes and simulation routes with metadata.
       """
       # Copy logic from original routes.py list_routes function
       ...


   @router.get("/{route_id}", response_model=RouteResponse)
   async def get_route(
       route_id: str,
       route_manager: RouteManager = Depends(get_route_manager)
   ) -> RouteResponse:
       """
       Get detailed information for a specific route.

       Args:
           route_id: Unique route identifier

       Returns:
           RouteResponse: Complete route details including waypoints

       Raises:
           HTTPException: 404 if route not found
       """
       # Copy logic from original routes.py get_route function
       ...

   # Continue with activate_route, deactivate_routes, etc.
   EOF
   ```

3. **Copy and adapt logic** from original file:

   ```bash
   # Open original file in editor
   # Copy function implementations to new modules
   # Adjust imports as needed
   # Add type hints if missing
   # Add/update docstrings
   ```

4. **Extract shared logic to services** (if functions used in multiple places):

   ```bash
   # Example: Extract route statistics calculation
   cat > backend/starlink-location/app/services/route_stats.py <<'EOF'
   """
   Route statistics calculation service.

   Provides reusable functions for computing route progress, distances, ETAs.
   """
   from typing import Tuple
   from app.models.route import Route
   from app.models.position import Position


   def calculate_route_progress(
       route: Route,
       current_position: Position
   ) -> Tuple[float, int]:
       """
       Calculate progress along a route.

       Args:
           route: Route definition with waypoints
           current_position: Current GPS position

       Returns:
           Tuple of (progress_percent, current_waypoint_index)

       Example:
           >>> route = Route(waypoints=[...])
           >>> pos = Position(lat=37.7749, lon=-122.4194)
           >>> progress, waypoint = calculate_route_progress(route, pos)
           >>> print(f"Progress: {progress:.1f}% at waypoint {waypoint}")
       """
       # Implementation here
       ...
   EOF
   ```

5. **Create backward-compatible aggregator**:

   ```bash
   cat > backend/starlink-location/app/api/routes/__init__.py <<'EOF'
   """
   Routes API - Aggregated router for backward compatibility.

   This module maintains the same interface as the original routes.py,
   but internally delegates to focused sub-modules.
   """
   from fastapi import APIRouter

   from app.api.routes.management import router as management_router
   from app.api.routes.upload import router as upload_router
   from app.api.routes.stats import router as stats_router
   from app.api.routes.timing import router as timing_router
   from app.api.routes.cache import router as cache_router

   # Create composite router with same prefix as original
   router = APIRouter(prefix="/api/routes", tags=["routes"])

   # Include all sub-routers
   router.include_router(management_router)
   router.include_router(upload_router)
   router.include_router(stats_router)
   router.include_router(timing_router)
   router.include_router(cache_router)

   # Re-export any utility functions used elsewhere
   # (if original routes.py exported helper functions)
   EOF
   ```

6. **Update main application** to use new structure:

   ```bash
   # Edit backend/starlink-location/app/main.py
   # Change:
   #   from app.api import routes
   # To:
   #   from app.api import routes  # Now imports from __init__.py
   # No other changes needed if __init__.py maintains compatibility
   ```

7. **Verify all files under 300 lines**:

   ```bash
   find backend/starlink-location/app/api/routes -name "*.py" -exec wc -l {} \; | sort -n

   # Expected output:
   # 95 cache.py
   # 145 timing.py
   # 198 upload.py
   # 215 stats.py
   # 245 management.py
   # Total: ~900 lines (vs. original 1046)
   ```

8. **Commit work incrementally**:

   ```bash
   git add backend/starlink-location/app/api/routes/management.py
   git commit -m "refactor(api): extract route management endpoints"

   git add backend/starlink-location/app/api/routes/upload.py
   git commit -m "refactor(api): extract route upload endpoints"

   # Continue for each module...

   git add backend/starlink-location/app/api/routes/__init__.py
   git commit -m "refactor(api): create composite router for backward compatibility"

   # IMPORTANT: Do NOT delete original file yet - verify everything works first
   ```

**Output**: New modular structure created, committed incrementally.

---

### Step 5: Run Linters (Local)

**Goal**: Ensure code meets formatting and style standards.

**Procedure**:

1. **Run Black formatter** (Python files):

   ```bash
   cd backend/starlink-location

   # Format all files in routes module
   black app/api/routes/

   # Expected output:
   # reformatted app/api/routes/management.py
   # reformatted app/api/routes/stats.py
   # All done! ✨ 🍰 ✨

   # Commit formatting changes separately
   git add app/api/routes/
   git commit -m "style(api): apply Black formatting to routes module"
   ```

2. **Run ruff linter** (Python files):

   ```bash
   # Check for linting issues
   ruff check app/api/routes/

   # Auto-fix issues where possible
   ruff check --fix app/api/routes/

   # Expected output:
   # Found 3 errors (3 fixed, 0 remaining).

   # Common fixes:
   # - Unused imports removed
   # - Import order corrected
   # - Line length adjusted

   # Commit fixes
   git add app/api/routes/
   git commit -m "style(api): fix ruff linting issues in routes module"
   ```

3. **Run Prettier** (TypeScript/JavaScript files):

   ```bash
   cd frontend/mission-planner

   # Format specific component
   npx prettier --write "src/components/common/RouteMap.tsx"

   # Or format entire directory
   npx prettier --write "src/pages/"

   # Commit formatting
   git add src/
   git commit -m "style(frontend): apply Prettier formatting"
   ```

4. **Run ESLint** (TypeScript/JavaScript files):

   ```bash
   cd frontend/mission-planner

   # Lint and auto-fix
   npm run lint -- --fix

   # Or target specific file
   npx eslint --fix src/components/common/RouteMap.tsx

   # Commit fixes
   git add src/
   git commit -m "style(frontend): fix ESLint issues"
   ```

5. **Verify type coverage** (Python):

   ```bash
   # Install mypy if not present
   pip install mypy

   # Check type hints
   mypy app/api/routes/ --strict

   # Fix any type errors (add missing hints, correct types)
   # Commit fixes
   git add app/api/routes/
   git commit -m "fix(api): add missing type hints to routes module"
   ```

6. **Verify no suppression comments**:

   ```bash
   # Check for lint-disable comments (should return nothing)
   rg "# type: ignore|# noqa|# pylint: disable" backend/starlink-location/app/api/routes/
   rg "eslint-disable|@ts-ignore|@ts-noqa" frontend/mission-planner/src/

   # If found, fix underlying issue instead of suppressing
   ```

**Output**: All linting passes, code formatted consistently.

---

### Step 6: Rebuild & Smoke Test

**Goal**: Verify refactored code behaves identically to original.

**Procedure**:

1. **Rebuild Docker environment** (CRITICAL - don't skip):

   ```bash
   cd /home/brian/Projects/starlink-dashboard-dev

   # REQUIRED sequence (per CLAUDE.md)
   docker compose down && \
     docker compose build --no-cache && \
     docker compose up -d

   # Wait for healthy status
   watch -n 2 docker compose ps
   # Press Ctrl+C when all show "healthy"
   ```

2. **Verify basic health**:

   ```bash
   # Health check
   curl http://localhost:8000/health

   # Expected: {"status":"ok","mode":"simulation",...}

   # Prometheus metrics
   curl http://localhost:8000/metrics | head -20

   # API docs accessible
   curl -I http://localhost:8000/docs
   # Expected: HTTP/1.1 200 OK
   ```

3. **Execute smoke tests** from [contracts/smoke-test-checklist.md](./contracts/smoke-test-checklist.md):

   **For Backend API Refactoring** (routes.py example):

   ```bash
   # 2.3 Routes API Tests

   # List all routes
   curl -s http://localhost:8000/api/routes | jq '.'
   # Verify: Returns array of routes

   # Get specific route (use ID from list above)
   ROUTE_ID=$(curl -s http://localhost:8000/api/routes | jq -r '.[0].id')
   curl -s http://localhost:8000/api/routes/$ROUTE_ID | jq '.'
   # Verify: Returns route details with waypoints

   # Upload KML file (use sample)
   curl -X POST \
     -F "file=@data/sample_routes/simple-circular.kml" \
     http://localhost:8000/api/routes/upload | jq '.'
   # Verify: Returns success with new route ID

   # Activate route
   curl -X POST http://localhost:8000/api/routes/$ROUTE_ID/activate | jq '.'
   # Verify: Returns success message

   # Get route statistics
   curl -s http://localhost:8000/api/routes/$ROUTE_ID/stats | jq '.'
   # Verify: Returns stats with progress, distance, ETA

   # Deactivate all routes
   curl -X POST http://localhost:8000/api/routes/deactivate | jq '.'
   # Verify: Returns success message

   # Delete route
   curl -X DELETE http://localhost:8000/api/routes/$ROUTE_ID | jq '.'
   # Verify: Returns success message
   ```

   **For Frontend Component Refactoring**:

   ```bash
   # Navigate to component in browser
   open http://localhost:3000/routes

   # Manual verification checklist:
   # - [ ] Component renders without errors
   # - [ ] All UI elements present (buttons, tables, maps)
   # - [ ] Click interactions work (buttons, links, toggles)
   # - [ ] Data loads and displays correctly
   # - [ ] Form submissions work
   # - [ ] No console errors in browser DevTools
   ```

4. **Document smoke test results** in PR description:

   ```bash
   # Update PR with test results
   gh pr edit --add-label "smoke-tests-passed"

   # Add comment with detailed results
   gh pr comment --body "$(cat <<EOF
   ## Smoke Test Results

   **Test Category**: Backend API - Routes Module
   **Tested By**: brian
   **Date**: 2025-12-02
   **Environment**: Docker (simulation mode)

   ### Tests Performed

   - [x] List all routes (GET /api/routes) - PASSED
   - [x] Get route by ID (GET /api/routes/{id}) - PASSED
   - [x] Upload KML file (POST /api/routes/upload) - PASSED
   - [x] Activate route (POST /api/routes/{id}/activate) - PASSED
   - [x] Get route statistics (GET /api/routes/{id}/stats) - PASSED
   - [x] Deactivate routes (POST /api/routes/deactivate) - PASSED
   - [x] Delete route (DELETE /api/routes/{id}) - PASSED

   ### Verification Evidence

   All endpoints return expected responses. No behavior changes detected.
   Prometheus metrics continue to update correctly.

   ### Conclusion

   ✅ Refactoring successful - behavior preserved
   EOF
   )"
   ```

5. **If tests fail**:

   ```bash
   # Analyze failure
   docker compose logs -f starlink-location | tail -100

   # Fix issue in code
   # Re-run rebuild sequence
   docker compose down && docker compose build --no-cache && docker compose up -d

   # Re-test
   # Repeat until all tests pass
   ```

**Output**: All smoke tests pass, results documented in PR.

---

### Step 7: Finalize PR

**Goal**: Prepare PR for review and merge.

**Procedure**:

1. **Remove original file** (only after smoke tests pass):

   ```bash
   # NOW safe to delete original monolithic file
   git rm backend/starlink-location/app/api/routes.py
   git commit -m "refactor(api): remove original monolithic routes.py"
   ```

2. **Push all changes**:

   ```bash
   git push origin refactor/api-routes-py
   ```

3. **Mark PR ready for review**:

   ```bash
   # Convert from draft to ready
   gh pr ready

   # Or via web UI: Click "Ready for review" button
   ```

4. **Verify CI passes**:

   ```bash
   # Check CI status
   gh pr checks

   # Expected output:
   # lint-python    ✓ success
   # lint-frontend  ✓ success
   # lint-docs      ✓ success

   # If CI fails, fix issues and push again
   ```

5. **Request review** (if working with team):

   ```bash
   gh pr review --request-reviewer @teammate

   # Or self-approve if solo:
   gh pr review --approve
   ```

6. **Address feedback** (if changes requested):

   ```bash
   # Make requested changes
   git add .
   git commit -m "fix(api): address review feedback - clarify docstrings"
   git push origin refactor/api-routes-py

   # Re-request review
   gh pr review --request-reviewer @teammate
   ```

**Output**: PR ready for merge, CI passing, approvals obtained.

---

### Step 8: Merge & Track

**Goal**: Integrate changes and update tracking data.

**Procedure**:

1. **Merge PR**:

   ```bash
   # Squash merge (recommended for clean history)
   gh pr merge --squash --delete-branch

   # Or via web UI: Click "Squash and merge"
   ```

2. **Update tracking files**:

   ```bash
   git checkout 001-codebase-cleanup
   git pull origin 001-codebase-cleanup

   # Update code-files.json
   # (Automate this or manually edit)
   cat > specs/001-codebase-cleanup/tracking/code-files.json <<EOF
   [
     {
       "file_id": "cf-routes-py",
       "path": "backend/starlink-location/app/api/routes.py",
       "line_count": 0,
       "original_line_count": 1046,
       "language": "python",
       "module_type": "api",
       "violation_status": "validated",
       "refactoring_priority": "P0_critical",
       "violation_severity": "none",
       "has_justification": false,
       "completed_at": "2025-12-02T18:00:00Z"
     }
   ]
   EOF

   # Update tasks.json
   cat > specs/001-codebase-cleanup/tracking/tasks.json <<EOF
   [
     {
       "task_id": "task-routes-py",
       "title": "Split routes.py into route modules (<300 lines each)",
       "target_files": ["backend/starlink-location/app/api/routes.py"],
       "violation_type": "size",
       "status": "completed",
       "pr_number": 42,
       "completed_at": "2025-12-02T18:00:00Z"
     }
   ]
   EOF

   git add specs/001-codebase-cleanup/tracking/
   git commit -m "docs(tracking): mark routes.py refactoring complete"
   git push origin 001-codebase-cleanup
   ```

3. **Calculate progress**:

   ```bash
   # Count remaining violations
   rg "# TODO: Refactor" backend/ docs/ frontend/ | wc -l

   # Update progress metric
   echo "Refactoring Progress: 1/26 files complete (3.8%)"
   ```

4. **Select next file** and repeat workflow.

**Output**: Changes merged, tracking updated, ready for next file.

---

## 4. Example Walkthrough

### Real Example: Refactoring `backend/starlink-location/app/api/routes.py` (1046 lines)

This example demonstrates the complete workflow on an actual violation.

#### Step 1: Select & Assess

```bash
# Current state
wc -l backend/starlink-location/app/api/routes.py
# Output: 1046 backend/starlink-location/app/api/routes.py

# Identify route groups
rg "@router\.(get|post|put|delete)" backend/starlink-location/app/api/routes.py -n

# Output analysis:
# Lines 50-200: Route listing and CRUD (get, activate, deactivate)
# Lines 201-400: File upload, download, delete
# Lines 401-600: Statistics and progress tracking
# Lines 601-800: Timing profile management
# Lines 801-1046: ETA cache operations

# Plan: 5 modules @ 150-250 lines each
```

#### Step 2: Create Branch & PR

```bash
git checkout 001-codebase-cleanup
git checkout -b refactor/api-routes-py
git push -u origin refactor/api-routes-py

gh pr create --draft \
  --title "refactor(api): split routes.py into focused modules" \
  --body "[See Step 3 template above]"
```

#### Step 3: Refactor - Extract Management Module

```bash
# Create directory
mkdir -p backend/starlink-location/app/api/routes

# Extract management endpoints
cat > backend/starlink-location/app/api/routes/management.py <<'EOF'
"""Route management endpoints - listing, activation, deactivation."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.models.route import RouteResponse, RouteListResponse
from app.services.route_manager import get_route_manager, RouteManager

router = APIRouter(tags=["routes"])


@router.get("/", response_model=RouteListResponse)
async def list_routes(
    route_manager: RouteManager = Depends(get_route_manager)
) -> RouteListResponse:
    """
    List all available routes.

    Returns both uploaded KML routes and simulation routes with metadata
    including waypoint counts, distance, and active status.
    """
    routes = await route_manager.list_routes()
    return RouteListResponse(routes=routes)


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: str,
    route_manager: RouteManager = Depends(get_route_manager)
) -> RouteResponse:
    """
    Get detailed information for a specific route.

    Args:
        route_id: Unique route identifier (filename without extension)

    Returns:
        RouteResponse with complete route data including waypoints

    Raises:
        HTTPException: 404 if route not found
    """
    route = await route_manager.get_route(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return route


@router.post("/{route_id}/activate")
async def activate_route(
    route_id: str,
    route_manager: RouteManager = Depends(get_route_manager)
) -> dict:
    """
    Activate a route for simulation following.

    Deactivates any previously active route and sets this route as active.
    Position simulation will begin following waypoints.

    Args:
        route_id: Route to activate

    Returns:
        Success message with route details

    Raises:
        HTTPException: 404 if route not found
    """
    success = await route_manager.activate_route(route_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return {"message": f"Route {route_id} activated", "route_id": route_id}


@router.post("/deactivate")
async def deactivate_routes(
    route_manager: RouteManager = Depends(get_route_manager)
) -> dict:
    """
    Deactivate all routes.

    Position simulation will stop following any route and enter free movement.
    """
    await route_manager.deactivate_all()
    return {"message": "All routes deactivated"}
EOF

# Verify line count
wc -l backend/starlink-location/app/api/routes/management.py
# Output: 95 lines ✓

# Commit
git add backend/starlink-location/app/api/routes/management.py
git commit -m "refactor(api): extract route management endpoints"
```

#### Step 4: Extract Remaining Modules

```bash
# Repeat extraction for upload.py, stats.py, timing.py, cache.py
# (Similar process, copy functions from original routes.py)

# Create __init__.py aggregator
cat > backend/starlink-location/app/api/routes/__init__.py <<'EOF'
"""Routes API - Aggregated router."""

from fastapi import APIRouter

from app.api.routes.management import router as management_router
from app.api.routes.upload import router as upload_router
from app.api.routes.stats import router as stats_router
from app.api.routes.timing import router as timing_router
from app.api.routes.cache import router as cache_router

router = APIRouter(prefix="/api/routes", tags=["routes"])

router.include_router(management_router)
router.include_router(upload_router)
router.include_router(stats_router)
router.include_router(timing_router)
router.include_router(cache_router)
EOF

git add backend/starlink-location/app/api/routes/
git commit -m "refactor(api): create composite routes router"
```

#### Step 5: Format & Lint

```bash
cd backend/starlink-location

# Format with Black
black app/api/routes/
git add app/api/routes/
git commit -m "style(api): apply Black formatting to routes module"

# Lint with ruff
ruff check --fix app/api/routes/
git add app/api/routes/
git commit -m "style(api): fix ruff linting issues"

# Push changes
git push origin refactor/api-routes-py
```

#### Step 6: Rebuild & Test

```bash
# CRITICAL: Full rebuild
docker compose down && docker compose build --no-cache && docker compose up -d

# Wait for healthy
docker compose ps

# Smoke test routes
curl http://localhost:8000/api/routes | jq '.'
# ✓ Returns route list

curl http://localhost:8000/api/routes/simple-circular | jq '.'
# ✓ Returns route details

curl -X POST http://localhost:8000/api/routes/simple-circular/activate | jq '.'
# ✓ Activates route

curl http://localhost:8000/api/routes/simple-circular/stats | jq '.'
# ✓ Returns statistics

curl -X POST http://localhost:8000/api/routes/deactivate | jq '.'
# ✓ Deactivates all routes

# ALL TESTS PASS ✓
```

#### Step 7: Finalize & Merge

```bash
# Remove original file
git rm backend/starlink-location/app/api/routes.py
git commit -m "refactor(api): remove original monolithic routes.py"
git push origin refactor/api-routes-py

# Mark ready for review
gh pr ready

# Verify CI
gh pr checks
# ✓ All checks passed

# Self-approve (or request team review)
gh pr review --approve

# Merge
gh pr merge --squash --delete-branch
```

#### Step 8: Track Progress

```bash
# Update tracking
git checkout 001-codebase-cleanup
git pull origin 001-codebase-cleanup

# Update progress: 1 of 26 files complete (3.8%)
echo "Progress: 1/26 (3.8%)" > specs/001-codebase-cleanup/PROGRESS.txt
git add specs/001-codebase-cleanup/PROGRESS.txt
git commit -m "docs(tracking): mark routes.py complete"
git push origin 001-codebase-cleanup

# Select next file: app/api/pois.py (1092 lines)
```

**Result**: Successfully reduced 1046-line file to 5 modules (95, 145, 198, 215, 245 lines). All tests pass, behavior unchanged.

---

## 5. Common Patterns

### Pattern 1: FastAPI Route Decomposition

**Use when**: Python API file >300 lines with multiple route groups.

**Strategy**:

```
Original: app/api/routes.py (1000+ lines)
Target:   app/api/routes/ directory

Split by:
1. CRUD operations (list, get, create, update, delete)
2. Functional domains (management, upload, statistics)
3. Resource types (routes vs. timing profiles vs. cache)

Result:
app/api/routes/
├── __init__.py       # Composite router
├── management.py     # CRUD operations
├── upload.py         # File operations
├── stats.py          # Calculations
└── [domain].py       # Other logical groups
```

**Template**:

```python
# app/api/routes/management.py
"""Route management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from app.services.route_manager import get_route_manager

router = APIRouter(tags=["routes"])

@router.get("/")
async def list_routes(...):
    """List all routes."""
    ...

@router.get("/{id}")
async def get_route(id: str, ...):
    """Get route by ID."""
    ...

@router.post("/{id}/activate")
async def activate_route(id: str, ...):
    """Activate route."""
    ...
```

```python
# app/api/routes/__init__.py
"""Composite router for backward compatibility."""

from fastapi import APIRouter
from app.api.routes.management import router as management_router
from app.api.routes.upload import router as upload_router

router = APIRouter(prefix="/api/routes", tags=["routes"])
router.include_router(management_router)
router.include_router(upload_router)
```

---

### Pattern 2: React Component Decomposition

**Use when**: React component >300 lines with mixed concerns.

**Strategy**:

```
Original: MissionDetailPage.tsx (450 lines)
Target:   Split into hooks + sub-components

Extract:
1. Custom hooks (data fetching, actions, form state)
2. Sub-components (header, table, sidebar)
3. Utilities (formatting, validation)

Result:
pages/
├── MissionDetailPage.tsx      # Main layout (150 lines)
hooks/
├── useMissionData.ts          # Data fetching hook (80 lines)
├── useMissionActions.ts       # Action handlers (70 lines)
components/mission/
├── MissionHeader.tsx          # Header section (60 lines)
├── MissionLegsTable.tsx       # Legs table (120 lines)
└── MissionMetadata.tsx        # Metadata sidebar (80 lines)
```

**Template**:

```typescript
// hooks/useMissionData.ts
import { useState, useEffect } from 'react';

export const useMissionData = (missionId: string) => {
  const [mission, setMission] = useState<Mission | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    fetchMission(missionId)
      .then(setMission)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [missionId]);

  return { mission, loading, error };
};
```

```typescript
// pages/MissionDetailPage.tsx
import { useMissionData } from '@/hooks/useMissionData';
import { MissionHeader } from '@/components/mission/MissionHeader';
import { MissionLegsTable } from '@/components/mission/MissionLegsTable';

export const MissionDetailPage = () => {
  const { id } = useParams();
  const { mission, loading, error } = useMissionData(id);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <div>
      <MissionHeader mission={mission} />
      <MissionLegsTable legs={mission.legs} />
    </div>
  );
};
```

---

### Pattern 3: Service Layer Extraction

**Use when**: Multiple files share complex logic (calculations, validations).

**Strategy**:

```
Extract shared logic from multiple route/component files into services.

Before:
- routes.py has calculate_eta() (50 lines)
- pois.py has calculate_eta() (50 lines, duplicated)
- stats.py has calculate_eta() (50 lines, duplicated)

After:
services/
└── eta_calculator.py
    └── calculate_eta() (50 lines, single source of truth)

routes.py, pois.py, stats.py all import from eta_calculator
```

**Template**:

```python
# app/services/eta_calculator.py
"""ETA calculation service - reusable across multiple modules."""

from typing import Tuple
from datetime import datetime, timedelta
from app.models.position import Position
from app.models.route import Waypoint


def calculate_eta(
    current_position: Position,
    target_waypoint: Waypoint,
    current_speed_knots: float
) -> Tuple[datetime, timedelta]:
    """
    Calculate ETA to target waypoint.

    Args:
        current_position: Current GPS position
        target_waypoint: Destination waypoint
        current_speed_knots: Current speed in knots

    Returns:
        Tuple of (eta_datetime, time_remaining)

    Example:
        >>> pos = Position(lat=37.7749, lon=-122.4194)
        >>> waypoint = Waypoint(lat=37.8044, lon=-122.2712)
        >>> eta, remaining = calculate_eta(pos, waypoint, 450)
        >>> print(f"ETA: {eta}, Time: {remaining}")
    """
    distance_nm = haversine_distance(
        current_position.lat, current_position.lon,
        target_waypoint.lat, target_waypoint.lon
    )

    if current_speed_knots == 0:
        raise ValueError("Cannot calculate ETA with zero speed")

    hours_remaining = distance_nm / current_speed_knots
    time_remaining = timedelta(hours=hours_remaining)
    eta_datetime = datetime.now() + time_remaining

    return eta_datetime, time_remaining
```

```python
# app/api/routes/stats.py (using service)
from app.services.eta_calculator import calculate_eta

@router.get("/{route_id}/eta")
async def get_route_eta(route_id: str, ...):
    """Get ETA to next waypoint."""
    current_pos = get_current_position()
    next_waypoint = get_next_waypoint(route_id)
    speed = get_current_speed()

    eta, remaining = calculate_eta(current_pos, next_waypoint, speed)

    return {"eta": eta.isoformat(), "time_remaining": str(remaining)}
```

---

### Pattern 4: Documentation Splitting

**Use when**: Markdown file >300 lines.

**Strategy**:

```
Original: docs/API-REFERENCE.md (999 lines)
Target:   Focused sub-documents

Split by:
1. API domain (routes, pois, missions, flight-status)
2. Logical sections (getting started, endpoints, examples, troubleshooting)

Result:
docs/api/
├── README.md             # Overview + quick start
├── routes.md             # Routes API endpoints
├── pois.md               # POIs API endpoints
├── missions.md           # Missions API endpoints
└── flight-status.md      # Flight status API
```

**Template**:

```markdown
<!-- docs/api/README.md -->
# API Reference

## Overview

This directory contains API documentation for all backend endpoints.

## Quick Start

```bash
# Start services
docker compose up -d

# Access API docs
open http://localhost:8000/docs
```

## API Domains

- [Routes API](./routes.md) - Route management and KML upload
- [POIs API](./pois.md) - Point of Interest CRUD and ETAs
- [Missions API](./missions.md) - Mission planning and execution
- [Flight Status API](./flight-status.md) - Departure/arrival state

## Common Patterns

All API endpoints follow these conventions:
- Base URL: `http://localhost:8000`
- Authentication: None (development mode)
- Response format: JSON
- Error codes: Standard HTTP status codes

For detailed endpoint specifications, see the linked domain documentation.
```

```markdown
<!-- docs/api/routes.md -->
# Routes API

Complete reference for route management endpoints.

## Endpoints

### List All Routes

**GET** `/api/routes`

Returns array of all available routes (uploaded and simulation).

**Response**:
```json
[
  {
    "id": "simple-circular",
    "name": "Simple Circular Route",
    "waypoint_count": 14,
    "distance_km": 50.2,
    "active": false
  }
]
```

### Get Route by ID

**GET** `/api/routes/{route_id}`

Returns detailed route information including waypoints.

**Parameters**:
- `route_id` (path, required): Route identifier

**Response**:
```json
{
  "id": "simple-circular",
  "name": "Simple Circular Route",
  "waypoints": [...],
  "metadata": {...}
}
```

[Continue with remaining endpoints...]
```

---

### Pattern 5: Backward Compatibility via Re-Export

**Use when**: Breaking module into sub-modules but external code imports from original.

**Strategy**:

```
Problem: External code imports functions from original monolithic file.
Solution: Create __init__.py that re-exports all public APIs.

Before:
from app.api.routes import list_routes, get_route, activate_route

After (split):
from app.api.routes.management import list_routes, get_route, activate_route
from app.api.routes.upload import upload_route, delete_route

Compatibility layer (app/api/routes/__init__.py):
from app.api.routes.management import list_routes, get_route, activate_route
from app.api.routes.upload import upload_route, delete_route

# External code still works:
from app.api.routes import list_routes, get_route, activate_route
```

**Template**:

```python
# app/api/routes/__init__.py
"""
Routes API - Backward compatibility layer.

This module maintains the same public API as the original routes.py,
but internally delegates to focused sub-modules.

Public API functions and routers are re-exported for backward compatibility.
"""

# Re-export main router (most common usage)
from app.api.routes.composite import router

# Re-export utility functions (if any were exported from original)
from app.api.routes.utils import parse_route_id, validate_kml

# Re-export models (if any were defined in original)
from app.api.routes.models import RouteResponse, RouteListResponse

__all__ = [
    "router",              # Main router for FastAPI app.include_router()
    "parse_route_id",      # Utility function
    "validate_kml",        # Utility function
    "RouteResponse",       # Model
    "RouteListResponse",   # Model
]
```

---

## 6. Troubleshooting

### Issue 1: Docker Not Reflecting Code Changes

**Symptoms**:
- Code changes don't affect API behavior
- Old errors persist after fixes
- Tests pass locally but fail in Docker

**Root Cause**: Docker is serving cached Python bytecode or stale image layers.

**Solution**:

```bash
# ALWAYS use this full rebuild sequence after Python changes
docker compose down && \
  docker compose build --no-cache && \
  docker compose up -d

# Verify new code is running
docker compose exec starlink-location cat /app/app/api/routes/management.py | head -20

# Check container logs for errors
docker compose logs -f starlink-location
```

**Prevention**: Add to your workflow muscle memory:
- Edit Python file → Full rebuild → Test
- Never skip `--no-cache` flag
- Never use `docker compose restart` for code changes

---

### Issue 2: Circular Import Errors

**Symptoms**:
```
ImportError: cannot import name 'RouteManager' from partially initialized module 'app.services.route_manager'
```

**Root Cause**: Module A imports Module B, which imports Module A.

**Diagnosis**:

```bash
# Find circular dependencies
rg "from app\." backend/starlink-location/app/ -n | \
  awk '{print $2}' | \
  sort | uniq -c | sort -rn

# Visualize import graph (requires pydeps)
pip install pydeps
pydeps app/api/routes/ --max-depth 2
```

**Solution**:

**Option 1: Use Dependency Injection**
```python
# Before (circular)
# app/services/route_manager.py
from app.services.poi_manager import POIManager

class RouteManager:
    def __init__(self):
        self.poi_manager = POIManager()  # Creates circular reference

# app/services/poi_manager.py
from app.services.route_manager import RouteManager

class POIManager:
    def __init__(self):
        self.route_manager = RouteManager()  # Circular!

# After (dependency injection)
# app/services/route_manager.py
class RouteManager:
    def __init__(self, poi_manager: 'POIManager'):  # Inject, don't import
        self.poi_manager = poi_manager

# app/main.py (wire dependencies)
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager

poi_mgr = POIManager()
route_mgr = RouteManager(poi_manager=poi_mgr)
```

**Option 2: Extract Shared Interface**
```python
# Create shared interface module
# app/interfaces/manager_protocol.py
from typing import Protocol

class RouteManagerProtocol(Protocol):
    def get_route(self, route_id: str) -> Route: ...

class POIManagerProtocol(Protocol):
    def get_poi(self, poi_id: str) -> POI: ...

# Use protocols instead of concrete classes
# app/services/route_manager.py
from app.interfaces.manager_protocol import POIManagerProtocol

class RouteManager:
    def __init__(self, poi_manager: POIManagerProtocol):
        self.poi_manager = poi_manager
```

---

### Issue 3: Import Errors After Splitting Files

**Symptoms**:
```
ModuleNotFoundError: No module named 'app.api.routes.management'
```

**Root Cause**: Missing `__init__.py` or incorrect import paths.

**Solution**:

```bash
# Ensure __init__.py exists in all directories
find backend/starlink-location/app -type d -exec touch {}/__init__.py \;

# Verify Python can import module
docker compose exec starlink-location python -c "from app.api.routes.management import router; print(router)"

# Check PYTHONPATH
docker compose exec starlink-location python -c "import sys; print('\n'.join(sys.path))"

# Expected output should include:
# /app
# /app/app
```

---

### Issue 4: Type Checking Errors with MyPy

**Symptoms**:
```
error: Incompatible return value type (got "Optional[Route]", expected "Route")
```

**Root Cause**: Missing type hints or incorrect type annotations.

**Solution**:

```python
# Before (incorrect)
def get_route(route_id: str):  # Missing return type
    route = route_manager.get(route_id)
    if route is None:
        raise HTTPException(404)
    return route  # MyPy doesn't know this is non-None

# After (correct)
def get_route(route_id: str) -> Route:  # Explicit return type
    route = route_manager.get(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route  # MyPy knows this branch returns Route

# For Optional returns
def get_route_optional(route_id: str) -> Optional[Route]:
    return route_manager.get(route_id)  # Can return None

# Use assert for type narrowing
route: Optional[Route] = get_route_optional("id")
assert route is not None  # Type narrows to Route
print(route.name)  # No type error
```

**Run type checker**:
```bash
mypy app/api/routes/ --strict --show-error-codes
```

---

### Issue 5: Smoke Tests Fail After Refactoring

**Symptoms**:
- API returns 404 for existing endpoints
- Response schema doesn't match expected
- Timeout errors

**Diagnosis**:

```bash
# Check if endpoint exists in OpenAPI schema
curl http://localhost:8000/openapi.json | jq '.paths'

# Check exact route registration
docker compose exec starlink-location python -c "
from app.main import app
for route in app.routes:
    print(f'{route.methods} {route.path}')
"

# Check logs for startup errors
docker compose logs starlink-location | rg "ERROR|WARNING"
```

**Common Causes & Fixes**:

**1. Router not included in main app**
```python
# app/main.py - Missing include_router
from app.api.routes import router as routes_router  # Forgot this line
app.include_router(routes_router)  # Add this
```

**2. Incorrect prefix in sub-router**
```python
# Before (double prefix: /api/routes/api/routes/...)
router = APIRouter(prefix="/api/routes", tags=["routes"])
# In __init__.py:
composite_router = APIRouter(prefix="/api/routes")  # Duplicate!
composite_router.include_router(router)

# After (correct)
router = APIRouter(tags=["routes"])  # No prefix in sub-router
# In __init__.py:
composite_router = APIRouter(prefix="/api/routes")  # Prefix only here
composite_router.include_router(router)
```

**3. Missing dependency injection**
```python
# Before (fails at runtime)
@router.get("/")
async def list_routes():
    route_manager = get_route_manager()  # Not injected, fails

# After (correct)
@router.get("/")
async def list_routes(
    route_manager: RouteManager = Depends(get_route_manager)
):
    routes = await route_manager.list_routes()
    return routes
```

---

### Issue 6: Linter/Formatter Conflicts

**Symptoms**:
- Black formats code, ruff complains
- ESLint and Prettier conflict
- Pre-commit hooks fail with conflicting rules

**Solution**:

**Python (Black + ruff)**:
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py312']

[tool.ruff]
line-length = 88  # Match Black
select = ["E", "F", "I"]
ignore = ["E501"]  # Black handles line length

[tool.ruff.lint.isort]
profile = "black"  # Compatible with Black
```

**TypeScript/JavaScript (ESLint + Prettier)**:
```json
// .eslintrc.json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "prettier"  // Must be last - disables conflicting ESLint rules
  ]
}
```

**Run formatters before linters**:
```bash
# Python
black app/ && ruff check --fix app/

# TypeScript
npx prettier --write src/ && npx eslint --fix src/
```

---

### Issue 7: Git Merge Conflicts During Refactoring

**Symptoms**:
- Multiple refactoring PRs conflict with each other
- Base branch changed while working on refactoring

**Prevention**:

```bash
# 1. Keep PRs small (1-3 files)
# 2. Merge frequently (don't let PRs sit open)
# 3. Rebase before finalizing PR

git checkout refactor/api-routes-py
git fetch origin
git rebase origin/001-codebase-cleanup

# Resolve conflicts if any
# Then force-push (safe for feature branches)
git push --force-with-lease origin refactor/api-routes-py
```

**Resolution**:

```bash
# If conflict occurs during merge
git checkout 001-codebase-cleanup
git pull origin 001-codebase-cleanup
git merge refactor/api-routes-py

# Conflict in app/main.py (both PRs modified imports)
git status
# both modified: app/main.py

# Edit app/main.py, resolve conflict markers
# Keep both imports if needed
nano app/main.py

# Stage resolution
git add app/main.py
git commit -m "merge: resolve conflict in main.py imports"
git push origin 001-codebase-cleanup
```

---

## 7. Command Reference

### Quick Command Cheat Sheet

```bash
# ============================================================================
# PROJECT SETUP
# ============================================================================

# Start Docker environment
docker compose up -d

# Stop Docker environment
docker compose down

# Full rebuild (REQUIRED after Python code changes)
docker compose down && docker compose build --no-cache && docker compose up -d

# Check container health
docker compose ps

# View logs
docker compose logs -f starlink-location

# ============================================================================
# GIT WORKFLOW
# ============================================================================

# Create feature branch
git checkout 001-codebase-cleanup
git checkout -b refactor/[scope]-[filename]
git push -u origin refactor/[scope]-[filename]

# Commit changes
git add [files]
git commit -m "refactor([scope]): [description]"
git push origin refactor/[scope]-[filename]

# Create draft PR
gh pr create --draft --title "refactor([scope]): [title]" --body "[description]"

# Mark PR ready
gh pr ready

# Check CI status
gh pr checks

# Merge PR
gh pr merge --squash --delete-branch

# ============================================================================
# PYTHON LINTING & FORMATTING
# ============================================================================

# Format with Black
black backend/starlink-location/app/

# Lint with ruff
ruff check backend/starlink-location/app/

# Auto-fix ruff issues
ruff check --fix backend/starlink-location/app/

# Type check with mypy
mypy backend/starlink-location/app/ --strict

# Run all Python checks
black app/ && ruff check --fix app/ && mypy app/

# ============================================================================
# TYPESCRIPT/JAVASCRIPT LINTING & FORMATTING
# ============================================================================

# Format with Prettier
cd frontend/mission-planner
npx prettier --write "src/**/*.{ts,tsx}"

# Lint with ESLint
npm run lint

# Auto-fix ESLint issues
npm run lint -- --fix

# Run all frontend checks
npx prettier --write "src/**/*.{ts,tsx}" && npm run lint -- --fix

# ============================================================================
# MARKDOWN LINTING & FORMATTING
# ============================================================================

# Format with Prettier
npx prettier --write "docs/**/*.md"

# Lint with markdownlint
npx markdownlint-cli2 "docs/**/*.md"

# Auto-fix markdownlint issues
npx markdownlint-cli2-fix "docs/**/*.md"

# ============================================================================
# FILE ANALYSIS
# ============================================================================

# Count lines in file
wc -l [file]

# Count lines in directory
find [dir] -name "*.py" -exec wc -l {} \; | awk '{sum+=$1} END {print sum}'

# Find large files (>300 lines)
find . -name "*.py" -exec wc -l {} \; | awk '$1 > 300 {print}' | sort -rn

# Find functions in file
rg "^def |^async def |^class " [file]

# Find imports in file
rg "^from |^import " [file]

# Find files importing a module
rg "from app.api.routes import" backend/

# ============================================================================
# SMOKE TESTING
# ============================================================================

# Health check
curl http://localhost:8000/health | jq '.'

# List routes
curl http://localhost:8000/api/routes | jq '.'

# Get specific route
curl http://localhost:8000/api/routes/{route_id} | jq '.'

# Upload KML
curl -X POST -F "file=@data/sample_routes/simple-circular.kml" \
  http://localhost:8000/api/routes/upload | jq '.'

# Activate route
curl -X POST http://localhost:8000/api/routes/{route_id}/activate | jq '.'

# Get route stats
curl http://localhost:8000/api/routes/{route_id}/stats | jq '.'

# Deactivate routes
curl -X POST http://localhost:8000/api/routes/deactivate | jq '.'

# Delete route
curl -X DELETE http://localhost:8000/api/routes/{route_id} | jq '.'

# ============================================================================
# DEBUGGING
# ============================================================================

# Check Python syntax
docker compose exec starlink-location python -m py_compile /app/app/api/routes/management.py

# Test import
docker compose exec starlink-location python -c "from app.api.routes.management import router; print(router)"

# Check PYTHONPATH
docker compose exec starlink-location python -c "import sys; print('\n'.join(sys.path))"

# List registered routes
docker compose exec starlink-location python -c "
from app.main import app
for route in app.routes:
    print(f'{route.methods} {route.path}')
"

# View OpenAPI schema
curl http://localhost:8000/openapi.json | jq '.paths | keys'

# Watch logs for errors
docker compose logs -f starlink-location | rg "ERROR|WARNING|Traceback"

# ============================================================================
# TRACKING & PROGRESS
# ============================================================================

# Count violations remaining
find backend -name "*.py" -exec wc -l {} \; | awk '$1 > 300 {print}' | wc -l

# Calculate progress
echo "scale=2; (26 - $(find backend -name '*.py' -exec wc -l {} \; | awk '$1 > 300' | wc -l)) / 26 * 100" | bc

# List all refactoring PRs
gh pr list --label "refactoring" --state all

# View PR for specific file
gh pr list --search "routes.py" --state all
```

### Pre-Commit Hook Commands

```bash
# Install pre-commit framework
pip install pre-commit

# Install hooks from .pre-commit-config.yaml
pre-commit install

# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run ruff --all-files

# Skip hooks for emergency commit (use sparingly)
git commit --no-verify -m "emergency fix"
```

### Batch Operations

```bash
# Format all Python files
find backend/starlink-location/app -name "*.py" -exec black {} \;

# Fix all ruff issues
find backend/starlink-location/app -name "*.py" -exec ruff check --fix {} \;

# Count total lines in Python codebase
find backend/starlink-location/app -name "*.py" -exec cat {} \; | wc -l

# Find all TODO comments
rg "# TODO:|# FIXME:|# HACK:" backend/ docs/ frontend/

# Remove trailing whitespace
find . -name "*.py" -exec sed -i 's/[[:space:]]*$//' {} \;
```

---

## Appendix: Additional Resources

### Internal Documentation

- [spec.md](./spec.md) - Complete feature requirements
- [research.md](./research.md) - Detailed refactoring strategies
- [data-model.md](./data-model.md) - Entity definitions and workflows
- [contracts/validation-schema.yaml](./contracts/validation-schema.yaml) - Validation rules
- [contracts/smoke-test-checklist.md](./contracts/smoke-test-checklist.md) - Testing procedures
- [contracts/linting-config-requirements.md](./contracts/linting-config-requirements.md) - Linter setup

### External Resources

- **FastAPI Best Practices**: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- **React Component Design**: https://react.dev/learn/thinking-in-react
- **Black Formatter**: https://black.readthedocs.io/
- **Ruff Linter**: https://docs.astral.sh/ruff/
- **Prettier**: https://prettier.io/docs/
- **ESLint**: https://eslint.org/docs/latest/
- **Conventional Commits**: https://www.conventionalcommits.org/

### Books

- "Refactoring: Improving the Design of Existing Code" by Martin Fowler
- "Working Effectively with Legacy Code" by Michael Feathers
- "Clean Code" by Robert C. Martin

---

**Document Version**: 1.0
**Last Updated**: 2025-12-02
**Maintained By**: Claude Code Agent
