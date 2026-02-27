## Context

The codebase has two independent route rendering pipelines that both need to handle International Date Line (IDL) crossings:

1. **Frontend (React-Leaflet)**: `RouteMap` renders a base route via `RouteLayer` (which already has IDL handling) and an optional color-coded timeline overlay via `ColorCodedRoute` (which does not).

2. **Backend (Matplotlib + Cartopy)**: `_generate_route_map()` in `exporter/__main__.py` renders route segments with two code paths — a timed path (has IDL handling) and a fallback path for points without `expected_arrival_time` (no IDL handling).

The IDL normalization pattern is already established in both codebases. The fix is extending existing patterns to the two places that were missed.

## Goals / Non-Goals

**Goals:**
- Color-coded route overlay (green/yellow/red segments) renders correctly for IDL-crossing routes in the frontend
- PPTX route map renders correctly for IDL-crossing routes regardless of whether route points have timing data
- Reuse existing IDL detection and normalization patterns — no new algorithms

**Non-Goals:**
- Refactoring the overall IDL handling approach (the 0-360 normalization strategy works)
- Fixing POIMap IDL handling (separate component, separate concern)
- Handling routes that cross the IDL multiple times in a single leg (edge case not encountered in practice)

## Decisions

### 1. Frontend: Pass `isIDLCrossing` to `ColorCodedRoute`

**Decision**: Thread `isIDLCrossing` from `useMapState` through `RouteMap` into `ColorCodedRoute` as a prop. When true, normalize sample coordinates to 0-360 range before rendering Polylines.

**Rationale**: This follows the exact same pattern already used by `RouteLayer`, which receives `isIDLCrossing` and `normalizedCoordinates` from the parent. `ColorCodedRoute` was added later and missed this plumbing.

**Alternative considered**: Having `ColorCodedRoute` detect IDL crossings internally from its own sample data. Rejected because the detection should be centralized in `useMapState` — the map's bounds and center are already calculated in the normalized coordinate space, so the overlay must use the same space.

### 2. Backend: Extract IDL split logic into a helper

**Decision**: Extract the IDL segment-splitting logic (currently at lines 677-707 in `_generate_route_map`) into a small helper function, then call it from both the timed path and the fallback path.

**Rationale**: The fallback path (lines 652-660) needs the same split-at-180° logic. Duplicating the ~25 lines of splitting code would be fragile. A helper like `_plot_route_segment(ax, lon1, lat1, lon2, lat2, color, ...)` that internally checks for IDL crossings keeps both paths DRY.

**Alternative considered**: Just copy-pasting the IDL check into the fallback path. Rejected because maintaining two copies of the interpolation math is error-prone.

## Risks / Trade-offs

- **[Risk] ColorCodedRoute normalization could desync from RouteLayer normalization** → Mitigated by using the same `isIDLCrossing` flag from `useMapState`, ensuring both layers use the same coordinate space.

- **[Risk] Backend helper refactor could break existing timed-path rendering** → Mitigated by keeping the helper's logic identical to the existing inline code, just extracted. Existing test coverage in `test_pptx_builder.py` provides regression safety.

- **[Trade-off] We're not adding IDL handling to `POIMap.tsx`** → Accepted. POIMap is a separate component used on the POI Manager page with different data flow. It can be addressed separately if needed.
