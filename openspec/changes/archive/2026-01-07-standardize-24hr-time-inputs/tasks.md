# Implementation Tasks: Standardize 24-Hour Time Inputs

## Change ID

`standardize-24hr-time-inputs`

## Task List

### 1. Update Time Display Functions

- [x] Create `formatTime24Hour()` utility function in `lib/utils.ts`
  - Accept ISO 8601 datetime string
  - Return formatted string in 24-hour format (e.g., "2025-01-07 14:30:00")
  - Handle UTC timezone properly
- [x] Replace all `toLocaleString()` calls with explicit 24-hour format options
  - `KaOutageConfig.tsx` - lines 120, 129
  - `KuOutageConfig.tsx` - lines 123, 132
  - `RouteMap.tsx` - lines 121, 133
  - `RouteLayer.tsx` - line 84
- [x] Ensure consistent format pattern: "YYYY-MM-DD HH:mm:ss" or "YYYY-MM-DD HH:mm"

### 2. Update TimingSection Component

- [x] Add helper text to departure time input indicating 24-hour format
- [x] Update input placeholder or label to show example time in 24-hour format
- [x] Replace datetime-local input with separate date and time inputs
- [x] Use text input with pattern validation for time (ensures 24-hour format across all browsers)
- [x] Add real-time validation feedback for time format (HH:mm)
- [x] Add error state and visual indicators for invalid time format
- [x] Test time display and input in multiple browsers

### 3. Update KaOutageConfig Component

- [x] Add helper text to start time input indicating 24-hour format
- [x] Add helper text to end time input indicating 24-hour format
- [x] Add `step="60"` attribute to both datetime-local inputs
- [x] Update table header or display to clarify 24-hour format
- [x] Test time display and input in multiple browsers

### 4. Update KuOutageConfig Component

- [x] Add helper text to start time input indicating 24-hour format
- [x] Add helper text to end time input indicating 24-hour format
- [x] Add `step="60"` attribute to both datetime-local inputs
- [x] Update table header or display to clarify 24-hour format
- [x] Test time display and input in multiple browsers

### 5. Testing and Validation

- [x] Manual testing on Chrome - verify 24-hour format in inputs and displays
- [x] Manual testing on Firefox - verify 24-hour format in inputs and displays
- [x] Manual testing on Safari - verify 24-hour format in inputs and displays
- [x] Manual testing on Edge - verify 24-hour format in inputs and displays
- [x] Verify existing time validation logic still works
- [x] Verify ISO 8601 conversion to backend still works correctly
- [x] Test with various time values (early morning, afternoon, midnight, noon)
- [x] Verify no regressions in existing functionality

### 6. Documentation

- [x] Update component JSDoc comments to document 24-hour format requirement
- [x] Add inline code comments explaining format choices where helpful
- [x] Verify README or user documentation mentions 24-hour format (if applicable)

### 7. Build and Deploy

- [x] Run TypeScript type checking: `npm run type-check`
- [x] Run linting: `npm run lint`
- [x] Run build: `npm run build`
- [x] Verify no build errors or warnings

## Task Sequencing

Tasks should be completed in the following order:

1. **Task 1** (Time display functions) - Foundation for consistent display
2. **Tasks 2-4** (Component updates) - Can be done in parallel
3. **Task 5** (Testing) - After all component changes
4. **Task 6** (Documentation) - After implementation complete
5. **Task 7** (Build/Deploy) - Final validation

## Estimated Scope

- **Files Modified:** ~7 files
- **Lines Changed:** ~30-50 lines
- **New Utility Functions:** 1-2 functions
- **Testing Effort:** Manual browser testing required

## Dependencies

None - this change is self-contained within the frontend mission planner.

## Rollback Plan

If issues arise:
1. Revert utility function changes
2. Restore original `toLocaleString()` calls
3. Remove helper text additions
4. Rebuild frontend

All changes are frontend-only and can be reverted without backend impact.
