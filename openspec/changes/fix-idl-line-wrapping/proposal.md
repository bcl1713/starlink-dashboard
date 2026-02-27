## Why

Routes that cross the International Date Line (IDL) draw lines that wrap around the entire globe instead of taking the short path across 180°. This affects both the frontend color-coded timeline overlay (green/yellow/red segments) and the backend PPTX map generator's fallback rendering path. The base blue route line renders correctly — the bug is specifically in the timeline-to-map rendering in both pipelines.

## What Changes

- **Frontend `ColorCodedRoute.tsx`**: Add IDL-aware coordinate normalization to the color-coded route overlay. Currently receives raw timeline sample lat/lng and passes them directly to Leaflet Polylines with no IDL handling, causing wrapping. Needs the same 0-360 normalization pattern already used by `RouteLayer`.
- **Backend `exporter/__main__.py` fallback path**: Add IDL segment splitting to the route rendering fallback (lines 652-660) used when route points lack `expected_arrival_time`. The timed rendering path already handles IDL correctly; the fallback does not.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `timeline-preview`: Color-coded route visualization must handle IDL-crossing routes by normalizing coordinates, matching the behavior already required of the base route layer.
- `mission-export`: PPTX route map generation must handle IDL crossings in the untimed fallback rendering path, matching the behavior already present in the timed rendering path.

## Impact

- **Frontend**: `ColorCodedRoute.tsx` gains `isIDLCrossing` prop; `RouteMap.tsx` passes it through
- **Backend**: `exporter/__main__.py` `_generate_route_map()` fallback path adds IDL split logic
- **No API changes, no new dependencies, no breaking changes**
