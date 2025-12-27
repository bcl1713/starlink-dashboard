# Improve PPTX Slide Labels Proposal

## Summary

Update PowerPoint slide exports to use human-readable leg names and mission
metadata instead of technical IDs in headers and footers.

## Problem Statement

Currently, exported PowerPoint slides display technical identifiers that reduce
readability and professionalism:

1. **Slide titles** use leg IDs like "leg-1" instead of human-readable names
   like "Leg 1"
2. **Footer text** displays a generic "Organization" placeholder instead of
   meaningful mission context
3. **Mission context** is lost - viewers cannot easily identify which mission
   the slides belong to

This creates confusion during briefings and reduces the professional appearance
of deliverables.

## Proposed Solution

Enhance the PowerPoint generation logic to:

1. **Use leg name in slide titles**: Replace `timeline.mission_leg_id` with
   `mission.name` (e.g., "Leg 1 - Route Map" instead of "leg-1 - Route Map")
2. **Display mission metadata in footer**: Replace generic "Organization" with
   mission name and description in format: `{mission_name} | {mission_description}`
   (e.g., "26-05 | CONUS California")
3. **Preserve existing styling**: Maintain all current visual styling (gold
   bars, white text, 7pt font, positioning)

## Affected Components

### Backend

- `backend/starlink-location/app/mission/exporter/pptx_builder.py`:
  - `add_route_map_slide()` function (lines 139, 144-146, 202-207)
  - `add_timeline_table_slides()` function (lines 254, 287)

### Data Models

- Utilizes existing fields:
  - `MissionLeg.name`: Human-readable leg name (e.g., "Leg 1")
  - `Mission.name`: Mission identifier (e.g., "26-05")
  - `Mission.description`: Mission description (e.g., "CONUS California")

## Implementation Notes

### Current Behavior

**Route Map Slide:**

- Title: Uses `timeline.mission_leg_id` (e.g., "leg-1 - Route Map")
- Footer: Uses `mission.id | mission.description or "Organization"`

**Timeline Table Slide:**

- Title: Uses `timeline.mission_leg_id` (e.g., "leg-1 - Timeline")
- Footer: Uses `Date: {date} | mission.id | mission.description or "Organization"`

### Proposed Changes

**Route Map Slide:**

- Title: Use leg's `name` field (e.g., "Leg 1 - Route Map")
- Footer: Use parent mission's `name | description` when available (e.g., "26-05 | CONUS California"), otherwise leg's metadata

**Timeline Table Slide:**

- Title: Use leg's `name` field (e.g., "Leg 1 - Timeline")
- Footer: Keep date, use parent mission's `name | description` (e.g., "Date: 2025-01-15 | 26-05 | CONUS California")

### Edge Cases

1. **No mission object (standalone timeline)**: Fall back to `timeline.mission_leg_id`
2. **Missing mission name**: Fall back to `mission.id`
3. **Missing mission description**: Show only name without separator
4. **Multi-leg missions with parent_mission_id**: Load parent mission to get name and description
5. **Parent mission not found**: Fall back to leg's own metadata

## Design Decisions

### Decision 1: Footer Metadata Source (CONFIRMED)

When exporting slides for a multi-leg mission:
- **Slide title:** Use leg's name (e.g., "Leg 1 - Departure - Route Map")
- **Footer:** Use parent mission's name and description (e.g., "26-05 | CONUS California")

**Implementation:** When `parent_mission_id` is provided, load the parent mission
object to access its name and description. When not provided (standalone leg export),
use the leg's own metadata.

### Decision 2: Handling Missing Description (CONFIRMED)

When `mission.description` is None or empty:
- Show just the mission name without trailing separator (e.g., "26-05")
- Do not display "Organization" or other placeholder text

## Testing Strategy

1. **Unit tests**: Test slide generation with various mission configurations
2. **Integration tests**: Generate actual PPTX files and verify content
3. **Manual verification**: Export sample missions and review slides visually

## Backward Compatibility

This change only affects the visual presentation of PowerPoint slides and does
not modify:

- File formats (still PPTX)
- Slide structure or count
- Data model or API contracts
- Export file naming conventions
- Other export formats (CSV)

Existing automation that processes PPTX files will continue to work.

## Related Specifications

- `mission-export`: Defines PPTX export requirements and professional styling
- `mission-metadata`: Defines Mission and MissionLeg data structures
