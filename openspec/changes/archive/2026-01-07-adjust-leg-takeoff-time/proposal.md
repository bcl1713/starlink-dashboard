# Proposal: Adjust Leg Takeoff Time

## Change ID

`adjust-leg-takeoff-time`

## Summary

Enable mission planners to adjust the takeoff/departure time of a mission leg by specifying a new departure time in the UI. When a leg's departure time is changed, all waypoint times and timeline segments are automatically recalculated to reflect the new schedule while preserving the route geometry and speed profile.

## Problem Statement

Mission planners frequently need to adjust departure times due to operational changes (e.g., take off 40 minutes earlier/later due to weather, maintenance, or scheduling constraints). Currently, this requires regenerating KML files with updated timestamps, which is:

1. **Time-consuming**: Flight planners must manually update timestamps in KML files or run external tools
2. **Error-prone**: Manual timestamp editing risks introducing inconsistencies
3. **Disruptive**: Requires re-uploading route files and potentially losing other configuration
4. **Inflexible**: Cannot quickly evaluate different departure scenarios

The route geometry (waypoints, path, distances) remains identical—only the temporal dimension changes.

## Proposed Solution

Add an `adjusted_departure_time` field to the `MissionLeg` model that stores an optional override for the departure time. If set, this overrides the departure time extracted from the KML file.

### User Experience

**Frontend UI (Dedicated Timing Section):**
- Create a new "Timing" section on the leg detail page
- Display the **original departure time** (from KML) as read-only reference
- Provide an **editable departure time input** that:
  - Shows the current effective departure time (adjusted if set, otherwise original)
  - Allows user to enter a new departure time (UTC datetime)
  - Includes a "Reset to Original" button to clear the override
- Visual indication when departure time has been adjusted (badge/icon)
- Show calculated arrival time based on route duration
- **Warning**: If offset exceeds ±8 hours, show warning: "Large time shift detected. Consider requesting new route from flight planners."

**Example Workflow:**
1. User opens leg detail page for "Leg 6 Rev 6"
2. In "Timing" section, sees:
   - "Original Departure: 2025-10-27 16:45:00Z" (read-only)
   - "Current Departure: 2025-10-27 16:45:00Z" (editable)
3. User changes to: "2025-10-27 16:05:00Z" (40 minutes earlier)
4. System automatically:
   - Calculates offset: -40 minutes
   - Adjusts all waypoint times by -40 minutes
   - Regenerates timeline with adjusted times
   - Updates export documents with new times
5. User sees: "Adjusted Departure: 2025-10-27 16:05:00Z ⚠️ (40 min earlier)"
6. If user uploads new route KML, `adjusted_departure_time` is cleared

### Implementation Approach

**Backend Storage:**
- Add `adjusted_departure_time: Optional[datetime]` to `MissionLeg` model
- Backend calculates offset internally: `offset = adjusted - original`
- Timeline calculation applies offset to all route point timestamps

**Timeline Calculation:**
- Modify `derive_mission_window()` to:
  1. Extract original departure/arrival from KML route
  2. If `adjusted_departure_time` is set, calculate offset
  3. Apply offset to both departure and arrival times
  4. Return adjusted window for timeline calculation
- All downstream calculations (segments, advisories) use adjusted times

**API Updates:**
- `POST /api/v2/missions/{id}/legs`: Accept optional `adjusted_departure_time`
- `PATCH /api/v2/missions/{id}/legs/{leg_id}`: Accept optional `adjusted_departure_time`
- `PUT /api/v2/missions/{id}/legs/{leg_id}/route`: Clear `adjusted_departure_time` when route updated
- Set to `null` to clear adjustment and revert to original KML times

**Validation:**
- `adjusted_departure_time` must be valid ISO-8601 UTC datetime
- No artificial maximum offset imposed
- **Warning threshold**: If offset exceeds ±8 hours (±480 minutes), return warning in API response
- Frontend displays warning but allows user to proceed
- Adjusted departure + route duration must be valid datetime (no overflow)

**Route Update Behavior:**
- When route KML is updated via `PUT /route` endpoint:
  - Automatically clear `adjusted_departure_time` field
  - Assume new KML has accurate timing
  - User must re-apply adjustment if still needed

**Exports:**
- PPTX footer shows adjusted date
- CSV timeline uses adjusted timestamps
- All exports reflect adjusted schedule

### Key Behaviors

1. **Default State**: If `adjusted_departure_time` is `None`, use original KML times
2. **Override Active**: If `adjusted_departure_time` is set, calculate offset and apply uniformly
3. **Persistence**: Adjustment persists with leg configuration
4. **Route Updates**: When route KML is updated, `adjusted_departure_time` is automatically cleared
5. **Warnings**: Show warning if offset exceeds ±8 hours, but allow proceeding
6. **Clarity**: User never needs to calculate offsets manually; they just enter the desired departure time

## Benefits

1. **Intuitive UX**: Users specify departure time directly, not offsets
2. **Operational Flexibility**: Quickly test different departure scenarios without limitations
3. **Preservation of Work**: Satellite configs, AAR windows, outages remain intact during time adjustments
4. **Clear Intent**: Adjusted departure time is explicit in leg metadata
5. **Auditability**: Can see both original and adjusted times
6. **Consistency**: Single source of truth for time adjustments

## Scope

### In Scope
- Add `adjusted_departure_time` field to backend `MissionLeg` model
- Calculate offset internally and apply during timeline calculation
- Frontend UI with dedicated "Timing" section showing:
  - Original departure time (read-only)
  - Editable current departure time
  - "Reset to Original" button
  - Visual indicator for adjusted state
  - Warning for large offsets (>8 hours)
- Update API endpoints to accept `adjusted_departure_time`
- Clear `adjusted_departure_time` when route KML is updated
- Ensure exports use adjusted times
- Warning (not blocking) for offsets exceeding ±8 hours

### Out of Scope
- Modifying KML files on disk (offset applied at calculation time only)
- Automatic offset calculation based on current time
- Per-waypoint time adjustments (offset applies uniformly to entire leg)
- Time zone conversions (all times remain UTC as per current system)
- Adjusting arrival time independently (arrival auto-calculated from departure + duration)
- Hard limits on time adjustment magnitude

## Answered Questions

1. **UI Placement**: Dedicated "Timing" section on leg detail page
2. **Maximum Shift**: No artificial maximum. Warn if shift exceeds ±8 hours.
3. **Route Update Behavior**: Clear `adjusted_departure_time` when new KML uploaded
4. **Validation**: Warn for large offsets (>8 hours) but do not block

## Related Work

- **mission-export spec** - "Update Leg Route via KML Upload": When route updated, adjusted departure time will be cleared
- **RouteTimingProfile** (`app/models/route.py`): Already handles `departure_time` and `arrival_time`; offset calculation integrates here
- **Timeline Calculation** (`app/mission/timeline_builder/calculator.py`): Uses `derive_mission_window()` to extract times from route; offset applied here
- **KML Timing Extraction** (`app/services/kml/timing.py`): Extracts original timestamps from KML waypoint descriptions

## Success Criteria

1. User can set adjusted departure time (e.g., "2025-10-27 16:05:00Z") via frontend UI
2. System automatically calculates and applies offset to all waypoints
3. Timeline visualization shows adjusted segment times
4. Exported PPTX footer shows adjusted date
5. Exported CSV contains adjusted timestamps
6. Adjusted departure time persists when leg is reloaded
7. When route KML is updated, `adjusted_departure_time` is automatically cleared
8. User can click "Reset to Original" to clear adjustment
9. UI clearly shows both original and current/adjusted departure times in dedicated Timing section
10. Warning displayed (but not blocking) when offset exceeds ±8 hours

## Next Steps

1. Create spec delta for new capability: `leg-time-adjustment`
2. Define API contract for `adjusted_departure_time` in `MissionLeg` PATCH/POST
3. Update `derive_mission_window()` to calculate and apply offset
4. Design frontend UI component with dedicated Timing section
5. Add warning logic for large offsets (>8 hours)
6. Update route update endpoint to clear `adjusted_departure_time`
7. Update mission export to use adjusted times
