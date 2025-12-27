# Proposal: edit-mission-metadata

## Overview

Enable frontend users to edit mission name and description metadata through the web interface.

## Problem Statement

Currently, missions are created with a name and description, but there is no way for users to modify these fields after creation. Users need to be able to update mission metadata to:

- Fix typos in mission names or descriptions
- Update mission information as planning evolves
- Reflect changes in mission objectives or scope
- Keep mission records current and accurate

## Current State

**Backend (FastAPI):**
- Mission model (in `backend/starlink-location/app/mission/models.py:382-427`) has `name` and `description` fields
- `POST /api/v2/missions` creates missions with name/description
- `GET /api/v2/missions/{mission_id}` retrieves missions
- `DELETE /api/v2/missions/{mission_id}` deletes missions
- `PUT /api/v2/missions/{mission_id}/legs/{leg_id}` updates leg data
- **No endpoint exists to update mission-level metadata**

**Frontend (React/TypeScript):**
- Mission detail page (in `frontend/mission-planner/src/pages/MissionDetailPage.tsx:22-100`) displays mission name and description as read-only text
- No UI components exist for editing mission metadata
- Mission API service (in `frontend/mission-planner/src/services/missions.ts`) has create, get, delete, and leg operations
- **No update mission operation exists**

## Proposed Solution

Add a PATCH endpoint to update mission name and description, and create a corresponding frontend UI for inline editing.

**Backend:**
- Add `PATCH /api/v2/missions/{mission_id}` endpoint accepting partial Mission updates
- Support updating `name` and `description` fields only (reject other field changes)
- Validate that name is non-empty and meets ID validation constraints
- Update `updated_at` timestamp automatically
- Return updated Mission object

**Frontend:**
- Add inline edit UI on Mission Detail Page for name and description
- Add `updateMission` method to missions API service
- Add `useUpdateMission` React Query hook
- Implement edit/save/cancel interaction pattern
- Show loading states during save
- Handle validation errors

## Scope

### In Scope
- PATCH endpoint for mission name/description
- Frontend inline editing UI
- API client integration
- Input validation
- Error handling

### Out of Scope
- Editing other mission fields (created_at, metadata, legs)
- Bulk mission updates
- Mission renaming that changes mission ID
- Editing leg name/description (separate feature)
- Version history or audit trail
- Permissions/authorization

## Dependencies

None - this is a straightforward CRUD enhancement to existing mission API.

## Risks and Mitigations

**Risk:** Users accidentally overwrite mission data
**Mitigation:** Require explicit save action; provide cancel button

**Risk:** Concurrent edits by multiple users
**Mitigation:** Document that last-write-wins; future enhancement could add optimistic locking

**Risk:** Invalid names break mission references
**Mitigation:** Use existing validation; mission ID remains unchanged

## Success Criteria

- Users can click to edit mission name on detail page
- Users can click to edit mission description on detail page
- Changes are saved to backend via PATCH endpoint
- Mission list and detail pages reflect updated values
- Validation errors are shown clearly
- TypeScript compilation succeeds with no errors
- Backend tests verify PATCH endpoint behavior
