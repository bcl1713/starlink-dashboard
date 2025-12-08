# Refactoring Roadmap: Phases 1-3

## Phase 1: Pure Utilities (Low Risk, High Value)

**Goal:** Extract pure functions with zero manager/visualization dependencies

### 1.1 Create `formatting.py` (80-120 lines)

**Source:** exporter.py lines 135-177 + related utilities

**Candidates:**

- `_ensure_timezone(dt: datetime) -> datetime`
- `_mission_start_timestamp(timeline) -> datetime`
- `_format_utc(dt: datetime) -> str`
- `_format_eastern(dt: datetime) -> str`
- `_format_offset(delta: timedelta) -> str`
- `_format_seconds_hms(value: float | int) -> str`
- `_compose_time_block(moment, mission_start) -> str`
- `_humanize_metric_name(key: str) -> str`

**Benefits:**

- Reusable in other modules
- Easy to unit test
- No external dependencies except zoneinfo
- Clear, single responsibility

**Implementation:**

```python
# formatting.py
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo("America/New_York")

def ensure_timezone(value: datetime) -> datetime: ...
def mission_start_timestamp(timeline) -> datetime: ...
# ... etc
```

### 1.2 Create `excel_utils.py` (100-150 lines)

**Source:** package_exporter.py lines 33-102, 104-122

**Candidates:**

- `_create_mission_summary_sheet(wb, mission)`
- `_copy_worksheet_content(source_sheet, target_sheet)`
- `_add_error_sheet(wb, leg_idx, leg, error_message)`

**Benefits:**

- Isolated Excel manipulation
- Reusable in other mission modules
- Single responsibility

### 1.3 Create `transport_utils.py` (50-80 lines)

**Source:** exporter.py lines 67-194 + constants

**Candidates:**

- `TRANSPORT_DISPLAY` dict
- `STATE_COLUMNS` list
- `STATUS_COLORS` dict
- `_serialize_transport_list(transports)`
- `_is_x_ku_conflict_reason(reason)`
- `_segment_is_x_ku_warning(segment)`
- `_display_transport_state(state, warning_override=False)`

**Benefits:**

- Shared between exporter.py and package_exporter.py
- Consistent transport display across formats
- Easy to modify color schemes/display names

---

## Phase 2: Data Processing Layer (Medium Risk)

**Goal:** Separate data transformation from format generation

### 2.1 Create `data_builders.py` (180-220 lines)

**Source:** exporter.py lines 1287-1414

**Candidates:**

- `_segment_rows(timeline, mission) -> pd.DataFrame`
- `_advisory_rows(timeline, mission) -> pd.DataFrame`
- `_statistics_rows(timeline) -> pd.DataFrame`
- `_summary_table_rows(timeline, mission) -> pd.DataFrame`

**Dependencies:**

- pandas
- mission models
- formatting.py utilities
- transport_utils.py

**Benefits:**

- Decouples data from rendering
- Easier to test pandas logic
- Enables DataFrame caching
- Reusable for future analytics

### 2.2 Create `segment_processing.py` (200-250 lines)

**Source:** exporter.py lines 206-385

**Candidates:**

- `_aar_block_rows(timeline, mission, mission_start) -> list`
- `_parse_iso_timestamp(raw: str) -> datetime`
- `_build_aar_record(start, end, mission, timeline, mission_start) -> dict`
- `_segment_at_time(timeline, timestamp) -> TimelineSegment | None`
- `_get_detailed_segment_statuses(start_time, end_time, timeline) -> list`

**Dependencies:**

- mission models
- formatting.py
- transport_utils.py

**Benefits:**

- Isolates AAR logic
- Better testability
- Enables future segment analysis features

---

## Phase 3: Map/Chart Rendering (High Risk)

**Goal:** Abstract visualization dependencies

### 3.1 Create `map_utils.py` (300-350 lines)

**Source:** exporter.py lines 387-425, + map-related helpers

**Candidates:**

- `_interpolate_position_at_time(target_time, p1, p2)`
- `_base_map_canvas() -> bytes`
- Helper functions for IDL handling, bounds calculation, aspect ratio

**Dependencies:**

- matplotlib, cartopy, PIL
- mission models

**Benefits:**

- Centralizes geospatial logic
- Can be mocked in tests
- Reusable for future mapping features

### 3.2 Create `render_map.py` (400-500 lines)

**Source:** exporter.py lines 428-1119

**Candidates:**

- `generate_route_map`
  `(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes`

**Keep As:** Public function (currently `_generate_route_map()`)

**Dependencies:**

- matplotlib, cartopy
- mission models
- route_manager, poi_manager
- map_utils.py
- segment_processing.py (for status colors)
- transport_utils.py

**Benefits:**

- Isolates heavy visualization
- Can be mocked in tests
- Enables lazy loading

### 3.3 Create `render_chart.py` (200-250 lines)

**Source:** exporter.py lines 1122-1284

**Candidates:**

- `generate_timeline_chart(timeline) -> bytes`

**Keep As:** Public function (currently `_generate_timeline_chart()`)

**Dependencies:**

- matplotlib
- mission models
- transport_utils.py
