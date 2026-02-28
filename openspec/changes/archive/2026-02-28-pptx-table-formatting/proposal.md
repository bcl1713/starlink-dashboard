## Why

The PPTX timeline table slides have two formatting issues: the "Segment #" column header wraps unnecessarily and adds no value since the numbered rows are self-explanatory, and the 9pt data font size causes text overflow in several columns (Start Time, End Time, Reasons).

## What Changes

- Remove the "Segment #" column header text — leave the header cell blank while keeping the segment number data in rows
- Reduce table font size from 9pt (data) / 10pt (header) to 8pt for all cells to prevent column overflow

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `mission-export`: Table font sizing and segment column header display requirements are changing

## Impact

- Backend only: `backend/starlink-location/app/mission/exporter/pptx_builder.py` — header row rendering and font size constants
- No API changes, no frontend changes
- No structural changes to PPTX output (same columns, same layout)
