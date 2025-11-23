# Checklist for mission-leg-planning-ui

**Branch:** `feat/mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
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
    * feat/mission-leg-planning-ui
    ```
  - [x] If you are on a different branch, switch with:
    ```bash
    git checkout feat/mission-leg-planning-ui
    ```

---

## Phase 1: Backend Data Model Refactoring

### 1.1: Rename Mission to MissionLeg in models.py

- [x] Open `backend/starlink-location/app/mission/models.py`
- [x] Locate the `class Mission(BaseModel):` definition
- [x] Rename the class from `Mission` to `MissionLeg`:
  ```python
  class MissionLeg(BaseModel):
  ```
- [x] Update the docstring to reflect the rename
- [x] Save the file
- [x] Expected: File should now define `MissionLeg` instead of `Mission`

### 1.2: Create new Mission model in models.py

- [x] In the same file `backend/starlink-location/app/mission/models.py`
- [x] Add the new `Mission` model after the `MissionLeg` class:
  ```python
  class Mission(BaseModel):
      """Top-level mission container holding multiple mission legs."""

      id: str = Field(..., description="Unique mission identifier (UUID or slug)")
      name: str = Field(..., description="Human-readable mission name", min_length=1)
      description: Optional[str] = Field(default=None, description="Detailed mission description")
      legs: list[MissionLeg] = Field(default_factory=list, description="Ordered list of mission legs")
      created_at: datetime = Field(
          default_factory=lambda: datetime.now(timezone.utc),
          description="When mission was created (UTC, ISO-8601)",
      )
      updated_at: datetime = Field(
          default_factory=lambda: datetime.now(timezone.utc),
          description="When mission was last updated (UTC, ISO-8601)",
      )
      metadata: dict = Field(default_factory=dict, description="Custom metadata fields")

      model_config = {
          "json_schema_extra": {
              "example": {
                  "id": "operation-falcon-2025",
                  "name": "Operation Falcon",
                  "description": "Multi-leg transcontinental mission",
                  "legs": [],
                  "created_at": "2025-11-23T10:00:00Z",
                  "updated_at": "2025-11-23T10:00:00Z",
                  "metadata": {},
              }
          }
      }
  ```
- [x] Save the file
- [x] Expected: File now contains both `Mission` and `MissionLeg` models

### 1.3: Update MissionTimeline to MissionLegTimeline

- [x] In `backend/starlink-location/app/mission/models.py`
- [x] Rename `class MissionTimeline` to `class MissionLegTimeline`
- [x] Update all references to `mission_id` field docstrings to mention "leg"
- [x] Save the file

### 1.4: Update imports in routes.py

- [x] Open `backend/starlink-location/app/mission/routes.py`
- [x] Update the import statement:
  ```python
  from app.mission.models import Mission, MissionLeg, MissionLegTimeline, ...
  ```
- [x] Find all occurrences of `Mission` type hints in function signatures
- [x] Replace them with `MissionLeg` where appropriate
- [x] Save the file
- [x] Expected: No import errors, `MissionLeg` used for current mission operations

### 1.5: Update storage.py for hierarchical structure

- [x] Open `backend/starlink-location/app/mission/storage.py`
- [x] Update imports:
  ```python
  from app.mission.models import Mission, MissionLeg, MissionLegTimeline
  ```
- [x] Add new storage functions for Mission (top-level):
  ```python
  def get_mission_path(mission_id: str) -> Path:
      """Get the directory path for a mission."""
      return MISSIONS_DIR / mission_id

  def get_mission_file_path(mission_id: str) -> Path:
      """Get the file path for mission metadata."""
      return get_mission_path(mission_id) / "mission.json"

  def get_mission_legs_dir(mission_id: str) -> Path:
      """Get the legs directory for a mission."""
      return get_mission_path(mission_id) / "legs"

  def get_mission_leg_file_path(mission_id: str, leg_id: str) -> Path:
      """Get the file path for a specific leg."""
      return get_mission_legs_dir(mission_id) / f"{leg_id}.json"
  ```
- [x] Save the file
- [x] Expected: New path helper functions defined

### 1.6: Implement save_mission_v2 function

- [x] In `backend/starlink-location/app/mission/storage.py`
- [x] Add function to save top-level Mission:
  ```python
  def save_mission_v2(mission: Mission) -> dict:
      """Save a hierarchical mission with nested legs.

      Args:
          mission: Mission object with legs

      Returns:
          Dictionary with save metadata
      """
      mission_dir = get_mission_path(mission.id)
      mission_dir.mkdir(parents=True, exist_ok=True)

      legs_dir = get_mission_legs_dir(mission.id)
      legs_dir.mkdir(parents=True, exist_ok=True)

      # Save mission metadata (without legs to avoid duplication)
      mission_meta = mission.model_copy(update={"legs": []})
      mission_file = get_mission_file_path(mission.id)

      with open(mission_file, "w") as f:
          json.dump(mission_meta.model_dump(), f, indent=2, default=str)

      # Save each leg separately
      for leg in mission.legs:
          leg_file = get_mission_leg_file_path(mission.id, leg.id)
          with open(leg_file, "w") as f:
              json.dump(leg.model_dump(), f, indent=2, default=str)

      logger.info(f"Mission {mission.id} saved with {len(mission.legs)} legs")

      return {
          "mission_id": mission.id,
          "path": str(mission_dir),
          "leg_count": len(mission.legs),
          "saved_at": datetime.now(timezone.utc).isoformat(),
      }
  ```
- [x] Save the file
- [x] Expected: Function defined, no syntax errors

### 1.7: Implement load_mission_v2 function

- [x] In `backend/starlink-location/app/mission/storage.py`
- [x] Add function to load hierarchical Mission:
  ```python
  def load_mission_v2(mission_id: str) -> Optional[Mission]:
      """Load a hierarchical mission with all legs.

      Args:
          mission_id: ID of mission to load

      Returns:
          Mission object with legs loaded, or None if not found
      """
      mission_file = get_mission_file_path(mission_id)

      if not mission_file.exists():
          logger.warning(f"Mission {mission_id} not found at {mission_file}")
          return None

      # Load mission metadata
      with open(mission_file, "r") as f:
          mission_data = json.load(f)

      # Load all legs
      legs_dir = get_mission_legs_dir(mission_id)
      legs = []

      if legs_dir.exists():
          for leg_file in sorted(legs_dir.glob("*.json")):
              with open(leg_file, "r") as f:
                  leg_data = json.load(f)
                  legs.append(MissionLeg(**leg_data))

      mission_data["legs"] = legs
      mission = Mission(**mission_data)

      logger.info(f"Mission {mission_id} loaded with {len(legs)} legs")
      return mission
  ```
- [x] Save the file
- [x] Expected: Load function defined

### 1.8: Run backend tests

- [x] Run existing tests to ensure renaming didn't break anything:
  ```bash
  cd backend/starlink-location && python -m pytest tests/ -v
  ```
- [x] Expected: All tests pass or show clear errors to fix
- [x] If tests fail, fix import errors and model references

### 1.9: Commit Phase 1 changes

- [x] Stage all changes:
  ```bash
  git add backend/starlink-location/app/mission/models.py
  git add backend/starlink-location/app/mission/storage.py
  git add backend/starlink-location/app/mission/routes.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: refactor Mission to MissionLeg, add hierarchical Mission model

  - Rename Mission class to MissionLeg
  - Add new Mission model as container for multiple legs
  - Update MissionTimeline to MissionLegTimeline
  - Add hierarchical storage functions (save_mission_v2, load_mission_v2)
  - Update storage paths for missions/{id}/mission.json and legs/

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 1"
  ```
- [x] Push to remote:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```
- [x] Expected: Changes pushed successfully

---

## Phase 2: Backend API Implementation

### 2.1: Create routes_v2.py file

- [x] Create new file `backend/starlink-location/app/mission/routes_v2.py`
- [x] Add initial imports and router setup:
  ```python
  """Mission v2 API endpoints for hierarchical mission management."""

  import logging
  from typing import Optional
  from fastapi import APIRouter, HTTPException, Query, status
  from pydantic import BaseModel, Field

  from app.mission.models import Mission, MissionLeg
  from app.mission.storage import (
      save_mission_v2,
      load_mission_v2,
      delete_mission,
      mission_exists,
  )

  logger = logging.getLogger(__name__)

  router = APIRouter(prefix="/api/v2/missions", tags=["missions-v2"])
  ```
- [x] Save the file
- [x] Expected: New file created with basic structure

### 2.2: Implement POST /api/v2/missions endpoint

- [x] In `backend/starlink-location/app/mission/routes_v2.py`
- [x] Add create mission endpoint:
  ```python
  @router.post("", status_code=status.HTTP_201_CREATED, response_model=Mission)
  async def create_mission(mission: Mission) -> Mission:
      """Create a new hierarchical mission with legs.

      Args:
          mission: Mission object to create

      Returns:
          Created mission with 201 status
      """
      try:
          logger.info(f"Creating mission {mission.id}")
          save_mission_v2(mission)
          logger.info(f"Mission {mission.id} created successfully")
          return mission
      except Exception as e:
          logger.error(f"Failed to create mission: {e}")
          raise HTTPException(
              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
              detail="Failed to create mission",
          )
  ```
- [x] Save the file (check line count < 350)
- [x] Expected: POST endpoint defined

### 2.3: Implement GET /api/v2/missions endpoint

- [x] In `backend/starlink-location/app/mission/routes_v2.py`
- [x] Add list missions endpoint:
  ```python
  @router.get("", response_model=list[Mission])
  async def list_missions(
      limit: int = Query(10, ge=1, le=100),
      offset: int = Query(0, ge=0),
  ) -> list[Mission]:
      """List all missions.

      Args:
          limit: Maximum number to return
          offset: Number to skip

      Returns:
          List of missions
      """
      try:
          from pathlib import Path
          missions_dir = Path("data/missions")

          if not missions_dir.exists():
              return []

          missions = []
          for mission_dir in sorted(missions_dir.iterdir()):
              if mission_dir.is_dir():
                  mission = load_mission_v2(mission_dir.name)
                  if mission:
                      missions.append(mission)

          return missions[offset : offset + limit]
      except Exception as e:
          logger.error(f"Failed to list missions: {e}")
          raise HTTPException(
              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
              detail="Failed to list missions",
          )
  ```
- [x] Save the file
- [x] Expected: GET list endpoint defined

### 2.4: Implement GET /api/v2/missions/{id} endpoint

- [x] In `backend/starlink-location/app/mission/routes_v2.py`
- [x] Add get mission by ID endpoint:
  ```python
  @router.get("/{mission_id}", response_model=Mission)
  async def get_mission(mission_id: str) -> Mission:
      """Get a specific mission by ID.

      Args:
          mission_id: Mission ID to retrieve

      Returns:
          Mission object with all legs
      """
      mission = load_mission_v2(mission_id)

      if not mission:
          raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail=f"Mission {mission_id} not found",
          )

      return mission
  ```
- [x] Save the file
- [x] Expected: GET by ID endpoint defined

### 2.5: Register v2 router in main.py

- [ ] Open `backend/starlink-location/main.py`
- [ ] Add import:
  ```python
  from app.mission import routes_v2 as mission_routes_v2
  ```
- [ ] Find where routers are registered (around line 447)
- [ ] Add v2 router registration:
  ```python
  app.include_router(mission_routes_v2.router, tags=["Missions V2"])
  ```
- [ ] Save the file
- [ ] Expected: V2 API registered in main application

### 2.6: Test v2 endpoints manually

- [ ] Rebuild and restart Docker containers:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [ ] Wait for services to be healthy:
  ```bash
  docker compose ps
  ```
- [ ] Test create mission:
  ```bash
  curl -X POST http://localhost:8000/api/v2/missions \
    -H "Content-Type: application/json" \
    -d '{
      "id": "test-mission-1",
      "name": "Test Mission",
      "description": "Testing v2 API",
      "legs": []
    }'
  ```
- [ ] Expected: 201 Created response with mission JSON
- [ ] Test list missions:
  ```bash
  curl http://localhost:8000/api/v2/missions
  ```
- [ ] Expected: Array with test mission

### 2.7: Create package_exporter.py file

- [ ] Create `backend/starlink-location/app/mission/package_exporter.py`
- [ ] Add initial structure (keep under 350 lines):
  ```python
  """Mission package export utilities for creating portable mission archives."""

  import io
  import json
  import logging
  import zipfile
  from datetime import datetime, timezone
  from pathlib import Path
  from typing import Optional

  from app.mission.models import Mission
  from app.mission.storage import load_mission_v2, get_mission_path
  from app.mission.exporter import generate_timeline_export, TimelineExportFormat

  logger = logging.getLogger(__name__)


  class ExportPackageError(RuntimeError):
      """Raised when mission package export fails."""


  def export_mission_package(mission_id: str) -> bytes:
      """Export complete mission as zip archive.

      Package includes:
      - mission.json (top-level metadata)
      - legs/*.json (all leg configurations)
      - routes/*.kml (KML files for each leg)
      - pois/*.json (POI data for each leg)
      - exports/leg-{id}/ (PDF, XLSX, PPTX, CSV for each leg)
      - manifest.json (package metadata)

      Args:
          mission_id: Mission to export

      Returns:
          Zip file as bytes
      """
      mission = load_mission_v2(mission_id)

      if not mission:
          raise ExportPackageError(f"Mission {mission_id} not found")

      buffer = io.BytesIO()

      with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
          # Add mission metadata
          zf.writestr("mission.json", json.dumps(mission.model_dump(), indent=2, default=str))

          # Add manifest
          manifest = {
              "version": "1.0",
              "mission_id": mission.id,
              "mission_name": mission.name,
              "leg_count": len(mission.legs),
              "exported_at": datetime.now(timezone.utc).isoformat(),
          }
          zf.writestr("manifest.json", json.dumps(manifest, indent=2))

          # TODO: Add legs, routes, POIs, exports in subsequent tasks

      buffer.seek(0)
      return buffer.read()
  ```
- [ ] Save the file (check < 350 lines)

### 2.8: Add export endpoint to routes_v2.py

- [ ] Open `backend/starlink-location/app/mission/routes_v2.py`
- [ ] Add import:
  ```python
  from fastapi.responses import StreamingResponse
  from app.mission.package_exporter import export_mission_package
  ```
- [ ] Add endpoint:
  ```python
  @router.post("/{mission_id}/export")
  async def export_mission(mission_id: str) -> StreamingResponse:
      """Export mission as zip package."""
      try:
          zip_bytes = export_mission_package(mission_id)

          return StreamingResponse(
              io.BytesIO(zip_bytes),
              media_type="application/zip",
              headers={
                  "Content-Disposition": f'attachment; filename="{mission_id}.zip"'
              },
          )
      except Exception as e:
          logger.error(f"Export failed: {e}")
          raise HTTPException(
              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
              detail=str(e),
          )
  ```
- [ ] Save file (check < 350 lines)

### 2.9: Commit Phase 2 changes

- [ ] Stage all changes:
  ```bash
  git add backend/starlink-location/app/mission/routes_v2.py
  git add backend/starlink-location/app/mission/package_exporter.py
  git add backend/starlink-location/main.py
  ```
- [ ] Commit:
  ```bash
  git commit -m "feat: add v2 missions API and export endpoint

  - Create /api/v2/missions endpoints (CRUD)
  - Add hierarchical mission management
  - Implement basic package export (zip structure)
  - Register v2 router in main.py

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 2"
  ```
- [ ] Push:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```

---

## Phase 3: Frontend Project Setup

### 3.1: Initialize React + TypeScript project with Vite

- [ ] Create frontend directory:
  ```bash
  mkdir -p frontend/mission-planner
  cd frontend/mission-planner
  ```
- [ ] Initialize Vite project:
  ```bash
  npm create vite@latest . -- --template react-ts
  ```
- [ ] Expected: Vite project initialized with TypeScript

### 3.2: Install core dependencies

- [ ] Install dependencies:
  ```bash
  npm install react-router-dom @tanstack/react-query zustand
  npm install axios zod react-hook-form @hookform/resolvers
  npm install leaflet react-leaflet
  npm install -D @types/leaflet
  ```
- [ ] Expected: Dependencies installed in package.json

### 3.3: Install ShadCN/UI and Tailwind CSS

- [ ] Install Tailwind:
  ```bash
  npm install -D tailwindcss postcss autoprefixer
  npx tailwindcss init -p
  ```
- [ ] Initialize ShadCN:
  ```bash
  npx shadcn@latest init
  ```
  - [ ] Select: TypeScript
  - [ ] Select: Default style
  - [ ] Select: Neutral color
  - [ ] Select: CSS variables for colors
- [ ] Expected: tailwind.config.js and components.json created

### 3.4: Install dev dependencies

- [ ] Install testing and linting tools:
  ```bash
  npm install -D vitest @testing-library/react @testing-library/jest-dom
  npm install -D @playwright/test
  npm install -D eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin
  npm install -D prettier eslint-config-prettier
  npm install -D @types/node
  ```
- [ ] Expected: All dev dependencies installed

### 3.5: Configure ESLint with max-lines rule

- [ ] Create `.eslintrc.json`:
  ```json
  {
    "extends": [
      "eslint:recommended",
      "plugin:@typescript-eslint/recommended",
      "plugin:react/recommended",
      "prettier"
    ],
    "parser": "@typescript-eslint/parser",
    "plugins": ["@typescript-eslint", "react"],
    "rules": {
      "max-lines": ["error", 350],
      "react/react-in-jsx-scope": "off"
    },
    "settings": {
      "react": {
        "version": "detect"
      }
    }
  }
  ```
- [ ] Save file
- [ ] Expected: ESLint enforces 350-line limit

### 3.6: Configure Prettier

- [ ] Create `.prettierrc`:
  ```json
  {
    "semi": true,
    "trailingComma": "es5",
    "singleQuote": true,
    "printWidth": 80,
    "tabWidth": 2
  }
  ```
- [ ] Save file

### 3.7: Create project folder structure

- [ ] Create directory structure:
  ```bash
  mkdir -p src/components/{missions,legs,satellites,ui,common}
  mkdir -p src/hooks/{api,ui,utils}
  mkdir -p src/services
  mkdir -p src/types
  mkdir -p src/lib
  ```
- [ ] Expected: Folder structure matches CONTEXT.md

### 3.8: Create Dockerfile for frontend

- [ ] Create `frontend/mission-planner/Dockerfile`:
  ```dockerfile
  # Multi-stage build for production
  FROM node:20-alpine AS builder

  WORKDIR /app

  # Copy package files
  COPY package*.json ./

  # Install dependencies
  RUN npm ci

  # Copy source files
  COPY . .

  # Build for production
  RUN npm run build

  # Production stage
  FROM nginx:alpine

  # Copy built files
  COPY --from=builder /app/dist /usr/share/nginx/html

  # Copy nginx config
  COPY nginx.conf /etc/nginx/conf.d/default.conf

  EXPOSE 80

  CMD ["nginx", "-g", "daemon off;"]
  ```
- [ ] Save file

### 3.9: Update docker-compose.yml

- [ ] Open `docker-compose.yml` at repo root
- [ ] Add frontend service:
  ```yaml
  mission-planner:
    build:
      context: ./frontend/mission-planner
      dockerfile: Dockerfile
    ports:
      - "5173:80"
    depends_on:
      - starlink-location
    environment:
      - VITE_API_URL=http://localhost:8000
  ```
- [ ] Save file
- [ ] Expected: Frontend service defined in compose

### 3.10: Commit Phase 3 changes

- [ ] Stage changes:
  ```bash
  git add frontend/mission-planner/
  git add docker-compose.yml
  ```
- [ ] Commit:
  ```bash
  git commit -m "feat: initialize React TypeScript frontend with Vite

  - Create mission-planner React app with TypeScript
  - Install ShadCN/UI + Tailwind CSS
  - Configure ESLint with 350-line limit
  - Set up testing (Vitest, Playwright)
  - Add Dockerfile and docker-compose service
  - Create folder structure per SOLID principles

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 3"
  ```
- [ ] Push:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```

---

## Phase 4-8: Implementation Continues

> **Note:** Phases 4-8 involve extensive frontend component development,
> API integration, and testing. Each phase will have 50-100+ granular tasks.
>
> Due to the 350-line limit for this checklist file, the remaining phases
> will be documented in separate checklist files:
>
> - `CHECKLIST-PHASE-4.md` — Core UI Components
> - `CHECKLIST-PHASE-5.md` — Satellite & AAR Configuration
> - `CHECKLIST-PHASE-6.md` — Export/Import UI
> - `CHECKLIST-PHASE-7.md` — Testing
> - `CHECKLIST-PHASE-8.md` — Wrap-Up
>
> These will be created as implementation progresses.

---

## Documentation Maintenance

- [ ] Update PLAN.md after completing each phase
- [ ] Update CONTEXT.md if new files, dependencies, or risks discovered
- [ ] Update dev/LESSONS-LEARNED.md when something surprising happens

---

## Pre-Wrap Checklist

All of the following must be checked before handoff to `wrapping-up-plan`:

- [ ] All phase checklists completed
- [ ] No TODOs remain in code
- [ ] Dev server runs without warnings or errors
- [ ] Backend tests pass
- [ ] Frontend tests pass
- [ ] E2E tests pass
- [ ] 350-line limit enforced (no files exceed limit)
- [ ] PLAN.md updated to "Completed" status
- [ ] CONTEXT.md finalized
