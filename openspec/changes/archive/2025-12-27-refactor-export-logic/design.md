# Design: Export Logic Refactoring

## Architecture

### Current Architecture

```
package/__main__.py
├── generate_mission_combined_pptx()
│   ├── 417 lines of PPTX generation
│   ├── Calls _generate_route_map() 2× per leg
│   ├── Creates slides with headers/footers/logos
│   ├── Builds timeline tables with pagination
│   └── Applies status coloring

exporter/__main__.py
├── generate_pptx_export()
│   ├── 383 lines of PPTX generation (nearly identical)
│   ├── Calls _generate_route_map() 1× per leg
│   ├── Creates slides with headers/footers/logos
│   ├── Builds timeline tables with pagination
│   └── Applies status coloring
├── generate_xlsx_export()
│   └── Calls _generate_route_map()
└── generate_pdf_export()
    └── Calls _generate_route_map()
```

### Proposed Architecture

```
exporter/pptx_builder.py (NEW)
├── create_pptx_presentation()
│   ├── Parameters: mission, timeline, route_manager, poi_manager, logo_path
│   └── Returns: Presentation object
├── add_title_slide()
├── add_route_map_slide()
├── add_timeline_table_slides()
│   ├── Handles pagination
│   ├── Applies status coloring
│   └── Uses pptx_styling helpers
└── _get_mission_metadata()

exporter/__main__.py (UPDATED)
├── generate_pptx_export()
│   └── Calls create_pptx_presentation()
├── _generate_route_map()
│   └── No changes (already reusable)
└── Other export functions (no changes)

package/__main__.py (UPDATED)
├── generate_mission_combined_pptx()
│   ├── Loops through legs
│   ├── Calls create_pptx_presentation() for each leg
│   └── Merges presentations
└── _add_combined_mission_exports_to_zip()
    ├── Implements map cache (dict[route_id, bytes])
    ├── Passes cache to export functions
    └── Clears cache after export complete
```

## Data Flow

### Map Caching Flow

```
export_mission_package()
  ├── Create map_cache = {}
  ├── For each leg:
  │   ├── Check map_cache[leg.route_id]
  │   │   ├── Hit: reuse cached bytes
  │   │   └── Miss: generate + store in cache
  │   └── Generate XLSX/PPTX/PDF with cache
  └── Clear cache (scoped to export operation)
```

### PPTX Generation Flow

```
generate_mission_combined_pptx(mission, ...)
  ├── Create presentation
  ├── Add mission title slide
  ├── For each leg:
  │   ├── Load leg timeline
  │   ├── Call create_pptx_presentation(leg, timeline, ...)
  │   │   ├── Returns Presentation with leg slides
  │   │   ├── Route map slide
  │   │   └── Timeline table slides (paginated)
  │   └── Append slides to main presentation
  └── Return combined presentation

generate_pptx_export(timeline, mission, ...)
  ├── Call create_pptx_presentation(mission, timeline, ...)
  └── Return presentation bytes
```

## Key Decisions

### Decision 1: Map Cache Scope

**Options:**

1. Global cache (persists across requests)
2. Per-export cache (scoped to single export operation)
3. No cache (status quo)

**Choice:** Per-export cache

**Rationale:**

- Simple to implement (pass `map_cache` dict as parameter)
- No memory leak concerns (cleared after export)
- Sufficient for main use case (single mission export generates same map 7×)
- Avoids complexity of cache invalidation

### Decision 2: PPTX Builder API

**Options:**

1. Builder class with stateful methods
2. Functional API with pure functions
3. Hybrid: main entry function + helper functions

**Choice:** Hybrid approach

**Rationale:**

- Entry function `create_pptx_presentation()` provides clean interface
- Helper functions (`add_title_slide`, `add_timeline_table_slides`) are
  composable
- No state to manage (presentation passed as parameter)
- Aligns with existing codebase patterns

### Decision 3: Presentation Merging

**Options:**

1. Merge slides from multiple presentations
2. Build single presentation with all slides
3. Use python-pptx Presentation.clone()

**Choice:** Build single presentation

**Rationale:**

- Simpler than merging (no slide duplication)
- Avoids potential layout/formatting issues from merging
- Cleaner code (single presentation object throughout)

## Component Design

### pptx_builder.py

```python
"""Reusable PowerPoint presentation builder for mission exports."""

def create_pptx_presentation(
    mission: Mission | None,
    timeline: MissionLegTimeline,
    parent_mission_id: str | None = None,
    route_manager: RouteManager | None = None,
    poi_manager: POIManager | None = None,
    logo_path: Path | None = None,
    map_cache: dict[str, bytes] | None = None,
) -> Presentation:
    """Generate PowerPoint presentation with map and timeline slides.

    Args:
        mission: Mission or leg object
        timeline: Timeline for this mission/leg
        parent_mission_id: Parent mission ID (for multi-leg exports)
        route_manager: Route manager for map generation
        poi_manager: POI manager for map markers
        logo_path: Path to logo image
        map_cache: Optional cache for generated maps (route_id -> bytes)

    Returns:
        Presentation object with all slides
    """
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.62)

    # Add route map slide
    add_route_map_slide(
        prs, timeline, mission, parent_mission_id,
        route_manager, poi_manager, logo_path, map_cache
    )

    # Add timeline table slides
    add_timeline_table_slides(
        prs, timeline, mission, logo_path
    )

    return prs


def add_route_map_slide(
    prs: Presentation,
    timeline: MissionLegTimeline,
    mission: Mission | None,
    parent_mission_id: str | None,
    route_manager: RouteManager | None,
    poi_manager: POIManager | None,
    logo_path: Path | None,
    map_cache: dict[str, bytes] | None,
) -> None:
    """Add route map slide to presentation."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Add styling
    add_header_bar(slide, 0, 0, 10, 0.15)
    add_footer_bar(slide, 0, 5.47, 10, 0.15)
    if logo_path:
        add_logo(slide, logo_path, 0.2, 0.02, 0.5, 0.5)

    # Add map image (with caching)
    route_id = mission.route_id if mission else None
    if route_id and map_cache and route_id in map_cache:
        map_bytes = map_cache[route_id]
    else:
        map_bytes = _generate_route_map(
            timeline, mission, parent_mission_id,
            route_manager, poi_manager
        )
        if route_id and map_cache is not None:
            map_cache[route_id] = map_bytes

    # Add map to slide
    map_stream = io.BytesIO(map_bytes)
    pic = slide.shapes.add_picture(map_stream, ...)
    # ... positioning logic


def add_timeline_table_slides(
    prs: Presentation,
    timeline: MissionLegTimeline,
    mission: Mission | None,
    logo_path: Path | None,
) -> None:
    """Add paginated timeline table slides to presentation."""
    timeline_df = _segment_rows(timeline, mission)

    if timeline_df.empty:
        return

    # Pagination logic (extracted from existing code)
    chunks = _paginate_timeline_rows(timeline_df)

    for chunk_idx, chunk in enumerate(chunks):
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # Add styling
        add_header_bar(slide, 0, 0, 10, 0.15)
        add_footer_bar(slide, 0, 5.47, 10, 0.15)
        if logo_path:
            add_logo(slide, logo_path, 0.2, 0.02, 0.5, 0.5)

        # Add table
        _add_timeline_table(slide, chunk, chunk_idx)


def _paginate_timeline_rows(
    df: pd.DataFrame,
    rows_per_slide: int = 7,
    min_rows_last_slide: int = 3,
) -> list[pd.DataFrame]:
    """Split timeline rows into chunks for pagination."""
    # ... pagination logic (extracted from existing code)


def _add_timeline_table(
    slide: Slide,
    chunk: pd.DataFrame,
    chunk_idx: int,
) -> None:
    """Add timeline table to slide with status coloring."""
    # ... table creation and styling logic
```

### package/__main__.py Updates

```python
def generate_mission_combined_pptx(
    mission: Mission,
    route_manager: RouteManager | None = None,
    poi_manager: POIManager | None = None,
    output_path: str | None = None,
) -> bytes | None:
    """Generate combined PPTX slides for entire mission."""
    from app.mission.exporter.pptx_builder import create_pptx_presentation

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.62)

    logo_path = Path(__file__).parent.parent.joinpath("assets", "logo.png")

    # Add mission title slide
    _add_mission_title_slide(prs, mission, logo_path)

    # Process each leg
    for leg in mission.legs:
        leg_timeline = load_mission_timeline(leg.id)
        if not leg_timeline:
            continue

        # Generate slides for this leg using shared builder
        leg_slides = create_pptx_presentation(
            mission=leg,
            timeline=leg_timeline,
            parent_mission_id=mission.id,
            route_manager=route_manager,
            poi_manager=poi_manager,
            logo_path=logo_path,
        )

        # Append leg slides to main presentation (skip title slide)
        for slide in leg_slides.slides:
            _copy_slide(prs, slide)

    # Save and return
    if output_path:
        prs.save(output_path)
        return None

    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output.read()
```

## Testing Strategy

### Unit Tests

- `test_create_pptx_presentation()`: Verify slide count, structure
- `test_add_route_map_slide()`: Verify map embedding
- `test_add_timeline_table_slides()`: Verify table content, pagination
- `test_map_caching()`: Verify cache hit/miss behavior

### Integration Tests

- Compare PPTX output byte-for-byte with baseline (if deterministic)
- Visual comparison of slides (manual inspection)
- Verify export time reduction with multi-leg missions

### Regression Tests

- All existing export tests must pass
- No new errors in export logs
- Verify "Failed to generate PPTX for leg" error no longer occurs

## Migration Plan

### Phase 1: Extract PPTX Builder

1. Create `pptx_builder.py` with extracted functions
2. Update `generate_pptx_export()` to use new builder
3. Test single-leg exports

### Phase 2: Update Combined Export

1. Update `generate_mission_combined_pptx()` to use new builder
2. Test multi-leg mission exports
3. Compare output with baseline

### Phase 3: Add Map Caching

1. Add `map_cache` parameter to export functions
2. Implement cache lookup/storage in `_add_route_map_slide()`
3. Measure performance improvement

### Phase 4: Cleanup

1. Remove old duplicated code
2. Update documentation
3. Final testing

## Performance Benchmarks

### Before Refactoring

- 2-leg mission export: ~35 seconds (7 map generations @ 5s each)
- 5-leg mission export: ~90 seconds (15 map generations)

### After Refactoring (Estimated)

- 2-leg mission export: ~15 seconds (2 map generations + cache hits)
- 5-leg mission export: ~30 seconds (5 map generations + cache hits)

### Measurement Points

- Log timestamp before/after each `_generate_route_map()` call
- Log cache hit/miss metrics
- Total export duration (from API request to response)
