# Proposal: Standardize Time Inputs to 24-Hour Format

## Change ID

`standardize-24hr-time-inputs`

## Why

The application displays all times in 24-hour format (e.g., "14:30" for 2:30 PM), but HTML5 `datetime-local` input fields default to 12-hour format with AM/PM selectors in many browsers. This creates inconsistent user experience where users view times in 24-hour format but must enter times using 12-hour format with AM/PM. The cognitive switching between formats increases mental load and error potential. Since this application targets professional users in aviation, maritime, and military contexts—where 24-hour format is standard—all time inputs and displays should use 24-hour format consistently.

## What Changes

- Replace browser-default `datetime-local` inputs with controlled inputs that guide users toward 24-hour format
- Add helper text and visual cues to clarify 24-hour format expectation (e.g., "HH:mm" or "24-hour format")
- Update all time display functions to consistently use 24-hour format with explicit locale options
- Standardize `toLocaleString()` calls to use `{ hour12: false }` option
- Add `step="60"` attribute to datetime inputs for 1-minute precision
- Create utility functions for consistent 24-hour time formatting

## Impact

- **Affected specs:** New spec `time-input-consistency` (no existing specs modified)
- **Affected code:**
  - Frontend: `frontend/mission-planner/src/lib/utils.ts` (new utility functions)
  - Frontend: `frontend/mission-planner/src/pages/LegDetailPage/TimingSection.tsx` (time input updates)
  - Frontend: `frontend/mission-planner/src/components/satellites/KaOutageConfig.tsx` (time input updates)
  - Frontend: `frontend/mission-planner/src/components/satellites/KuOutageConfig.tsx` (time input updates)
  - Frontend: `frontend/mission-planner/src/components/common/RouteMap.tsx` (time display updates)
  - Frontend: `frontend/mission-planner/src/components/common/RouteMap/RouteLayer.tsx` (time display updates)
- **User workflow:** Users experience consistent 24-hour time format throughout the application, reducing cognitive load
- **Breaking changes:** None - backend API unchanged; only frontend display/input behavior changes

## Summary

Standardize all time input fields in the mission planner frontend to use 24-hour format (HH:mm) for consistency with the 24-hour time display format already used throughout the application.

## Problem Statement

The application currently displays all times in 24-hour format (e.g., "14:30" for 2:30 PM), but HTML5 `datetime-local` input fields default to 12-hour format with AM/PM selectors in most browsers. This creates an inconsistent user experience where:

- Users view times in 24-hour format when reading data
- Users must think in 12-hour format with AM/PM when entering data
- The cognitive switching between formats increases mental load and potential for errors

### Current Behavior

**Display (24-hour format):**
- Timeline segments: "2025-01-07 14:30:00Z"
- Outage windows: "2025-01-07 08:00" displayed as local 24-hour time
- Map tooltips: "Time: 2025-01-07 14:30:00"

**Input (12-hour format in most browsers):**
- Departure time adjustment: `<input type="datetime-local">` renders with AM/PM picker
- Ka outage windows: `<input type="datetime-local">` renders with AM/PM picker
- Ku outage windows: `<input type="datetime-local">` renders with AM/PM picker

## Proposed Solution

Update all time input fields to consistently use 24-hour format by adding HTML5 attributes and browser-specific controls, and standardize time display to always show 24-hour format with "HH:mm" pattern.

### Affected Components

1. **TimingSection.tsx** - Departure time adjustment input
2. **KaOutageConfig.tsx** - Ka outage start/end time inputs
3. **KuOutageConfig.tsx** - Ku outage start/end time inputs
4. **Time Display Functions** - Standardize all `toLocaleString()` calls to use 24-hour format

### Implementation Approach

1. Replace browser-default `datetime-local` inputs with controlled inputs that enforce 24-hour format
2. Update all time display functions to consistently use 24-hour format with explicit locale options
3. Ensure backend compatibility (ISO 8601 format unchanged)
4. Maintain existing UTC timezone semantics

## Benefits

1. **Consistency** - Single time format throughout the application (24-hour)
2. **Reduced Cognitive Load** - Users don't switch between 12-hour and 24-hour mental models
3. **Clarity** - 24-hour format eliminates AM/PM ambiguity
4. **Professional Standard** - 24-hour format is standard in aviation, maritime, and military operations (the primary use cases)

## Risks and Mitigations

### Risk: Browser Support
- **Risk:** Some browsers may not properly support forced 24-hour format via attributes
- **Mitigation:** Test on major browsers (Chrome, Firefox, Safari, Edge); fall back to clear labeling if needed

### Risk: User Familiarity
- **Risk:** Users accustomed to 12-hour format may need adjustment period
- **Mitigation:** This application targets professional users (aviation, maritime, military) who typically use 24-hour format; documentation can clarify the format

### Risk: Existing Data
- **Risk:** Existing missions with time data could be affected
- **Mitigation:** No impact - all backend data uses ISO 8601 format; only frontend display changes

## Scope

### In Scope
- Update TimingSection departure time input to 24-hour format
- Update KaOutageConfig start/end time inputs to 24-hour format
- Update KuOutageConfig start/end time inputs to 24-hour format
- Standardize all time display functions to use 24-hour format
- Add helper utilities for consistent 24-hour time formatting

### Out of Scope
- Backend API changes (ISO 8601 format remains unchanged)
- Date picker changes (only time portion affected)
- Timezone conversion logic (UTC semantics unchanged)
- User preferences or settings (24-hour format is always used)

## Success Criteria

1. All time inputs display and accept 24-hour format (HH:mm)
2. All time displays use consistent 24-hour format (HH:mm)
3. No regressions in time validation or data submission
4. Browser compatibility maintained across Chrome, Firefox, Safari, Edge
5. All existing tests pass

## Dependencies

None - this is a frontend-only change that does not affect the backend API or data models.

## Related Work

- **leg-time-adjustment spec** - Uses departure time adjustment; will benefit from consistent format
- **mission-export spec** - Exports time data; display format should remain consistent

## Open Questions

1. Should we display a visual indicator or helper text to clarify the 24-hour format requirement?
   - **Recommendation:** Add subtle helper text "(HH:mm)" or "(24-hour format)" near inputs

2. Should we add client-side validation to enforce 24-hour format entry?
   - **Recommendation:** Yes, add validation to prevent invalid time formats

## Implementation Notes

### Technical Approach

The HTML5 `datetime-local` input type does not provide a standard way to force 24-hour format across all browsers. The format is determined by the user's browser locale and system preferences. To achieve consistency, we should:

1. **Add explicit step and pattern attributes** to guide input format
2. **Use helper text** to clarify expected format
3. **Standardize display** by replacing `toLocaleString()` with explicit 24-hour formatting
4. **Consider custom time picker** if browser inconsistency is problematic (future enhancement)

### Code Changes Summary

- Modify 3 components (TimingSection.tsx, KaOutageConfig.tsx, KuOutageConfig.tsx)
- Update utility functions for time formatting
- Add tests for 24-hour format validation
- Update component documentation
