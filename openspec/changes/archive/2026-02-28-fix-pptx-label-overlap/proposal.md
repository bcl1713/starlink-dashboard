## Why

When PPTX route maps have POI markers close together (e.g., an AAR track ending near a Ka outage point), their labels overlap and become unreadable. All labels currently use a fixed `+0.5°` geographic offset, with no collision detection or avoidance. This is a readability problem — users can't read either label when they overlap.

## What Changes

- Add the `adjustText` Python library as a dependency to automatically reposition overlapping labels on route map images
- Refactor label placement in `_generate_route_map()` to collect all text objects and pass them to `adjust_text()` for collision-free positioning
- Leader lines drawn from displaced labels to their markers so association remains clear
- Replace the fixed `+0.5°` offset with dynamic positioning that only moves labels when necessary

## Capabilities

### New Capabilities

- `map-label-layout`: Automatic label collision avoidance for PPTX route map POI markers using force-directed repositioning

### Modified Capabilities

- `mission-export`: Route map slide labels are now dynamically positioned to avoid overlap, with leader lines connecting displaced labels to their markers

## Impact

- **Code**: `backend/starlink-location/app/mission/exporter/__main__.py` — `_generate_route_map()` label placement (~lines 910-995)
- **Dependencies**: New Python dependency `adjustText` added to backend requirements
- **Output**: PPTX route map images will have repositioned labels when markers are close together; maps with spread-out markers will look the same as before
- **No API changes**: This is a rendering-only change
