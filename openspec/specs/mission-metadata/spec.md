# mission-metadata Specification

## Purpose
TBD - created by archiving change edit-mission-metadata. Update Purpose after archive.
## Requirements
### Requirement: PATCH mission metadata endpoint

The API SHALL provide a PATCH endpoint at `/api/v2/missions/{mission_id}` for updating mission name and description. The endpoint MUST accept a request body containing optional `name` and `description` fields, MUST validate that name is non-empty if provided, MUST update the mission's `updated_at` timestamp, and MUST return the updated Mission object with HTTP 200 on success.

**Rationale:** Users need to modify mission metadata after creation to fix typos, update objectives, and keep records current.

#### Scenario: Update mission name

**Given** a mission exists with id "operation-falcon-2025" and name "Operation Falcon"

**When** a PATCH request is sent to `/api/v2/missions/operation-falcon-2025` with body:
```json
{
  "name": "Operation Falcon - Updated"
}
```

**Then** the response has status code 200

**And** the response body contains the updated mission with `name` = "Operation Falcon - Updated"

**And** the mission's `updated_at` timestamp is updated to the current time

#### Scenario: Update mission description

**Given** a mission exists with id "operation-falcon-2025" and description "Multi-leg mission"

**When** a PATCH request is sent to `/api/v2/missions/operation-falcon-2025` with body:
```json
{
  "description": "Updated multi-leg transcontinental mission with AAR windows"
}
```

**Then** the response has status code 200

**And** the response body contains the updated mission with the new description

**And** the mission's `updated_at` timestamp is updated

#### Scenario: Update both name and description

**Given** a mission exists with id "operation-falcon-2025"

**When** a PATCH request is sent to `/api/v2/missions/operation-falcon-2025` with body:
```json
{
  "name": "Operation Falcon - Rev 2",
  "description": "Revised mission plan with updated route"
}
```

**Then** the response has status code 200

**And** the response body contains both updated fields

**And** the mission's `updated_at` timestamp is updated

#### Scenario: Reject empty mission name

**Given** a mission exists with id "operation-falcon-2025"

**When** a PATCH request is sent to `/api/v2/missions/operation-falcon-2025` with body:
```json
{
  "name": ""
}
```

**Then** the response has status code 422 (Validation Error)

**And** the error details indicate that name must be non-empty

#### Scenario: Mission not found

**Given** no mission exists with id "nonexistent-mission"

**When** a PATCH request is sent to `/api/v2/missions/nonexistent-mission` with any update body

**Then** the response has status code 404

**And** the error message indicates mission not found

### Requirement: Frontend mission metadata editing UI

The mission detail page SHALL provide inline editing controls for mission name and description. The UI MUST display the current values, MUST allow users to click to enter edit mode, MUST provide save and cancel buttons in edit mode, MUST show validation errors for invalid input, MUST display loading states during save operations, and MUST update the displayed values upon successful save.

**Rationale:** Users need a convenient way to edit mission metadata directly from the detail view without navigating to separate forms.

#### Scenario: Edit mission name inline

**Given** the user is viewing a mission detail page

**When** the user clicks on the mission name heading

**Then** the name becomes an editable text input

**And** the input is pre-filled with the current mission name

**And** save and cancel buttons appear

**When** the user modifies the name and clicks save

**Then** the updated name is sent to the backend via PATCH

**And** the mission name display updates to show the new value

**And** the edit mode is exited

#### Scenario: Edit mission description inline

**Given** the user is viewing a mission detail page

**When** the user clicks on the mission description text

**Then** the description becomes an editable textarea

**And** the textarea is pre-filled with the current description

**And** save and cancel buttons appear

**When** the user modifies the description and clicks save

**Then** the updated description is sent to the backend via PATCH

**And** the mission description display updates

**And** the edit mode is exited

#### Scenario: Cancel editing

**Given** the user is editing mission name or description

**When** the user clicks the cancel button

**Then** the edit mode is exited

**And** the original value is restored

**And** no API request is made

#### Scenario: Show validation error

**Given** the user is editing mission name

**When** the user enters an empty name and clicks save

**Then** a validation error message is displayed

**And** the input remains in edit mode

**And** no API request is made

#### Scenario: Show loading state during save

**Given** the user has modified the mission name

**When** the user clicks save

**Then** a loading indicator is shown

**And** the save button is disabled

**And** the user cannot edit the field until the save completes

**When** the save completes successfully

**Then** the loading indicator disappears

**And** the edit mode is exited

### Requirement: API client integration

The frontend missions API service SHALL include an `updateMission` method that accepts a mission ID and partial update object. The method MUST send a PATCH request to `/api/v2/missions/{missionId}`, MUST be type-safe using TypeScript interfaces, and MUST return a Promise resolving to the updated Mission object.

**Rationale:** Provides type-safe, reusable API integration for mission updates.

#### Scenario: API service updateMission method

**Given** the missions API service is imported

**When** `missionsApi.updateMission(missionId, updates)` is called

**Then** a PATCH request is sent to `/api/v2/missions/{missionId}`

**And** the request body contains the partial update fields

**And** the response is typed as `Mission`

#### Scenario: React Query hook for updates

**Given** a component uses the `useUpdateMission()` hook

**When** the mutation is triggered with mission updates

**Then** the API call is executed

**And** on success, the mission cache is invalidated

**And** the missions list cache is invalidated

**And** the UI re-fetches fresh mission data

