# Implementation Tasks

## Task Breakdown

1. **Add helper function to resolve mission metadata**
   - Create `_get_footer_metadata()` helper in `pptx_builder.py`
   - When `parent_mission_id` is provided: Load parent mission using `load_mission_v2()`
   - Extract name and description from parent mission (or leg if parent not found)
   - Handle missing description: return name without separator
   - Return formatted string: `"{name} | {description}"` or just `"{name}"`
   - Validation: Unit test with various scenarios (parent mission, standalone, missing values)

2. **Update `add_route_map_slide()` function in `pptx_builder.py`**
   - Replace slide title logic: use `mission.name` instead of `timeline.mission_leg_id`
   - Call `_get_footer_metadata()` to get formatted footer text
   - Update footer text parameter to use helper result
   - Add fallback to `timeline.mission_leg_id` when `mission=None`
   - Validation: Generate sample PPTX and verify slide title shows "Leg 1" instead of "leg-1"

3. **Update `add_timeline_table_slides()` function in `pptx_builder.py`**
   - Replace slide title logic: use `mission.name` instead of `timeline.mission_leg_id`
   - Call `_get_footer_metadata()` to get formatted footer text
   - Update footer text: `f"Date: {mission_date} | {footer_metadata}"`
   - Add fallback to `timeline.mission_leg_id` when `mission=None`
   - Validation: Generate sample PPTX and verify timeline slide title and footer

4. **Handle edge cases with fallback logic**
   - Test with `mission=None` (standalone timeline) - should fall back to `timeline.mission_leg_id`
   - Test with `mission.name=None` - should fall back to `mission.id`
   - Test with `mission.description=None` - should show name without separator
   - Test with `parent_mission_id` provided but parent mission not found - fall back to leg metadata
   - Test with `parent_mission_id` provided and parent found - use parent metadata
   - Validation: Unit tests for each edge case

5. **Add unit tests for updated slide generation**
   - Test: Slide title uses `mission.name` when available
   - Test: Footer uses parent mission metadata when `parent_mission_id` provided
   - Test: Footer uses leg metadata when no `parent_mission_id`
   - Test: Fallback to `timeline.mission_leg_id` when `mission=None`
   - Test: Fallback to `mission.id` when `mission.name` is None
   - Test: Handle missing description (no trailing separator)
   - Validation: All tests pass

6. **Manual integration testing**
   - Generate PPTX for single-leg mission with name "Leg 1" and description "Test Flight"
   - Verify slide title shows "Leg 1 - Route Map"
   - Verify footer shows "Leg 1 | Test Flight" (no parent mission)
   - Generate PPTX for multi-leg mission package with parent mission "26-05" description "CONUS California"
   - Verify each leg slide title uses leg name (e.g., "Leg 1 - Route Map")
   - Verify footer uses parent mission metadata (e.g., "26-05 | CONUS California")
   - Validation: Visual inspection of generated slides

7. **Update spec documentation**
   - Update `mission-export` spec to reflect new footer format requirements
   - Add scenario for human-readable leg names in slide titles
   - Add scenario for parent mission metadata in footers
   - Validation: `openspec validate --strict` passes

## Dependencies

- Task 1 must be done first (helper function)
- Tasks 2 and 3 depend on task 1
- Task 4 depends on tasks 1-3
- Task 5 depends on tasks 1-4
- Task 6 depends on tasks 1-3
- Task 7 can be done in parallel with task 6

## Validation Checklist

- [x] Slide titles use human-readable leg names (e.g., "Leg 1" not "leg-1")
- [x] Route map footer shows parent mission metadata when available
- [x] Timeline slide footer shows date and parent mission metadata
- [x] Footer falls back to leg metadata when no parent mission
- [x] Missing description handled correctly (no trailing separator)
- [x] Edge cases handled (None values, missing mission object, parent not found)
- [x] Unit tests pass
- [x] Integration tests pass (test framework verified, unrelated PDF/XLSX test failures pre-existing)
- [x] OpenSpec validation passes
- [x] No visual regressions (gold bars, white text, positioning unchanged)
