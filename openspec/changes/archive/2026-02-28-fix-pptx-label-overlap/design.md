## Context

Route map images in PPTX exports are rendered server-side using Matplotlib + Cartopy at 4K resolution (3840x2160 @ 300 DPI). POI markers (departure, arrival, mission events like AAR and Ka outages) are labeled with `ax.text()` calls using a fixed `+0.5°` geographic offset. When markers are geographically close, their labels overlap and become unreadable.

The label placement code lives in `_generate_route_map()` in `backend/starlink-location/app/mission/exporter/__main__.py` (~lines 910-995). There are three independent label-placement blocks: departure, arrival, and mission event POIs. Each uses the same hardcoded offset with no awareness of other labels.

## Goals / Non-Goals

**Goals:**
- Labels on route map images never overlap to the point of being unreadable
- Labels that don't collide remain positioned close to their markers (no unnecessary displacement)
- Displaced labels connect to their markers via leader lines for clear association
- Solution works across varying map extents (global routes vs. regional legs)

**Non-Goals:**
- Interactive/editable labels in PowerPoint (labels are baked into the PNG)
- Label styling changes (font size, color, background remain the same)
- Filtering or suppressing any labels — all POIs are important and must be shown
- Label placement for non-PPTX contexts (frontend map is interactive and handles this differently)

## Decisions

### 1. Use `adjustText` library for label repositioning

**Decision:** Add the `adjustText` Python package as a dependency and use its `adjust_text()` function to resolve label overlaps.

**Alternatives considered:**
- **Greedy 8-direction placement** (try N, NE, E, SE, S, SW, W, NW per label): Simple, no dependency, but doesn't guarantee resolution when multiple labels cluster. Would need custom bounding-box intersection logic.
- **Simulated annealing**: Optimal results but complex to implement and tune, overkill for 5-15 labels.
- **Manual offset heuristics**: Alternate label directions by index. Fragile — breaks as soon as POI positions change.

**Rationale:** `adjustText` is a well-maintained matplotlib companion library designed exactly for this use case. It uses iterative force-directed repulsion to push overlapping labels apart. For 5-15 labels, it runs in milliseconds. It also handles leader line drawing automatically.

### 2. Collect all labels before adjusting

**Decision:** Refactor the three separate label-placement blocks (departure, arrival, mission events) to collect all `ax.text()` objects into a single list, then pass the entire list to `adjust_text()` in one call.

**Rationale:** `adjustText` needs visibility into all labels to resolve collisions globally. The current pattern of three independent blocks can't coordinate. Collecting first, adjusting once, ensures departure/arrival labels don't collide with mission event labels.

### 3. Tune repulsion to minimize unnecessary movement

**Decision:** Configure `adjust_text()` with conservative force parameters so labels only move when they actually overlap. Use `force_text=(0.5, 0.5)` and `force_points=(0.5, 0.5)` as starting points, tuned to avoid scattering labels on sparse maps.

**Rationale:** On maps where labels don't collide, the output should look the same as it does today — labels near their markers. Aggressive repulsion would push labels apart unnecessarily on well-spaced maps.

### 4. Leader line styling

**Decision:** Use thin gray arrows (`arrowstyle='->'`, `color='gray'`, `lw=0.5`) connecting displaced labels to their markers. Only visible when a label has been moved away from its marker.

**Rationale:** Users need to tell which label belongs to which marker when labels are repositioned. Thin gray lines are unobtrusive and match the map's professional aesthetic.

## Risks / Trade-offs

- **New dependency** → `adjustText` is pure Python with no compiled extensions, MIT licensed, and depends only on matplotlib/numpy (already in the stack). Low integration risk.
- **Label positions differ from current output** → Even on non-colliding maps, positions may shift slightly due to the algorithm. Mitigated by conservative force parameters. Acceptable trade-off for guaranteed readability.
- **Edge case: many labels in a tiny area** → With 15+ labels clustered tightly, `adjustText` may push some labels far from their markers. Mitigated by leader lines maintaining association. This is better than the current state where none of the labels are readable.
- **Cartopy coordinate transforms** → `adjustText` works in display coordinates. Labels placed with `transform=ccrs.PlateCarree()` need care to ensure the adjustment respects the projection. The text objects should be collected after they're added to the axes so matplotlib has resolved their display positions.
