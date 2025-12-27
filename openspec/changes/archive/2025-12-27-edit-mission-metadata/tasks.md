# Tasks: edit-mission-metadata

Implementation checklist for mission metadata editing feature.

## Backend Tasks

- [x] **Add PATCH endpoint in routes_v2.py**
  - Location: `backend/starlink-location/app/mission/routes_v2.py`
  - Add `@router.patch("/{mission_id}", response_model=Mission)` handler
  - Accept Pydantic model with optional `name` and `description` fields
  - Load existing mission, apply updates, save, return updated mission
  - Update `updated_at` timestamp automatically
  - Handle 404 if mission not found
  - Handle 422 for validation errors (empty name)
  - Add logging for update operations

- [x] **Create Pydantic model for partial mission updates**
  - Location: `backend/starlink-location/app/mission/models.py`
  - Add `MissionUpdate` model with optional `name: Optional[str]` and `description: Optional[str]`
  - Add validator to ensure name is non-empty if provided
  - Ensure model excludes other mission fields (id, legs, created_at, etc.)

- [x] **Add backend integration tests**
  - Location: `backend/starlink-location/tests/integration/test_mission_routes_v2.py`
  - Test successful name update
  - Test successful description update
  - Test updating both fields
  - Test validation error on empty name
  - Test 404 on nonexistent mission
  - Test `updated_at` timestamp changes

## Frontend Tasks

- [x] **Add updateMission method to API service**
  - Location: `frontend/mission-planner/src/services/missions.ts`
  - Add `updateMission: async (id: string, updates: Partial<Mission>) => Mission`
  - Make PATCH request to `/api/v2/missions/${id}` with update body
  - Return response data

- [x] **Add TypeScript type for mission updates**
  - Location: `frontend/mission-planner/src/types/mission.ts`
  - Add `export interface UpdateMissionRequest { name?: string; description?: string; }` or reuse `Partial<Pick<Mission, 'name' | 'description'>>`

- [x] **Add useUpdateMission React Query hook**
  - Location: `frontend/mission-planner/src/hooks/api/useMissions.ts`
  - Add `useUpdateMission()` hook returning mutation
  - On success, invalidate `['missions']` and `['missions', missionId]` queries
  - Return mutation with `mutate` and `mutateAsync` functions

- [x] **Create EditableField component**
  - Location: `frontend/mission-planner/src/components/missions/EditableField.tsx`
  - Accept props: `value`, `onSave`, `isLoading`, `multiline?`, `placeholder?`
  - Manage local edit state (isEditing, editValue)
  - Render view mode: display value with click-to-edit affordance
  - Render edit mode: input/textarea with save/cancel buttons
  - Handle validation (non-empty for required fields)
  - Show loading spinner during save
  - Call onSave callback with new value

- [x] **Integrate EditableField into MissionDetailPage**
  - Location: `frontend/mission-planner/src/pages/MissionDetailPage.tsx`
  - Replace mission name heading with `<EditableField value={mission.name} onSave={handleUpdateName} />`
  - Replace mission description paragraph with `<EditableField value={mission.description} onSave={handleUpdateDescription} multiline />`
  - Add `handleUpdateName` and `handleUpdateDescription` functions using `useUpdateMission` hook
  - Handle errors (show alert or toast on failure)

- [ ] **Add frontend tests (optional but recommended)**
  - Location: `frontend/mission-planner/src/components/missions/EditableField.test.tsx`
  - Test click-to-edit interaction
  - Test save and cancel behavior
  - Test validation error display
  - Test loading state

## Validation & Quality

- [x] **Run backend type checking**
  - Execute: `cd backend/starlink-location && python -m mypy app/`
  - Fix any type errors

- [x] **Run backend tests**
  - Execute: `cd backend/starlink-location && pytest tests/integration/test_mission_routes_v2.py -v`
  - Ensure all new tests pass

- [x] **Run frontend type checking**
  - Execute: `cd frontend/mission-planner && npx tsc --noEmit`
  - Fix any TypeScript errors

- [x] **Run frontend build**
  - Execute: `cd frontend/mission-planner && npm run build`
  - Ensure build succeeds without errors

- [ ] **Manual testing**
  - Create a test mission
  - Edit mission name inline
  - Edit mission description inline
  - Test cancel button
  - Test validation error on empty name
  - Verify updates persist after page refresh

## Documentation

- [ ] **Update API documentation (optional)**
  - If API docs exist, document new PATCH endpoint
  - Include request/response examples

## Deployment Notes

- Backend changes require Docker rebuild: `docker compose down && docker compose build --no-cache && docker compose up -d`
- Frontend changes are hot-reloaded during development
- Test against running backend before merging
