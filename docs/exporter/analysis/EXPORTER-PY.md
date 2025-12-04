# Exporter Core Analysis (exporter.py)

## File Overview

### exporter.py (2220 lines)

**Primary Purpose:** Mission timeline export utilities transforming
`MissionLegTimeline` data into customer-facing deliverables (CSV, XLSX, PDF,
PPTX) with parallel timestamp formats (UTC, Eastern, T+ offsets).

**Primary Responsibility:** Single-leg/individual timeline export generation
with rich visualization and formatting

---

### Exporter: Core Functions by Category

#### Timestamp & Formatting Utilities (Lines 135-177)

- `_ensure_timezone()` - Converts naive datetimes to UTC
- `_mission_start_timestamp()` - Infers mission zero point from earliest segment
- `_format_utc()` - UTC string format: "YYYY-MM-DD HH:MMZ"
- `_format_eastern()` - Eastern time with DST awareness
- `_format_offset()` - T+/-HH:MM format relative to mission start
- `_format_seconds_hms()` - Converts seconds to HH:MM:SS format
- `_compose_time_block()` - Combines UTC, Eastern, and T+ offset

#### Transport Display & Validation (Lines 67-194)

- Transport display mappings: X-Band, CommKa, StarShield
- `_serialize_transport_list()` - Converts Transport enums to display names
- `_is_x_ku_conflict_reason()` - Identifies X-Ku conflict warnings
- `_segment_is_x_ku_warning()` - Flags X-Ku specific warnings
- `_display_transport_state()` - Transport state with warning override

#### Data Processing for Segments (Lines 206-385)

- `_aar_block_rows()` - Extracts AAR (After Action Report) blocks from
  statistics
- `_parse_iso_timestamp()` - ISO8601 timestamp parsing with fallback
- `_build_aar_record()` - Constructs AAR row data
- `_segment_at_time()` - Finds segment containing a given timestamp
- `_get_detailed_segment_statuses()` - Color-codes route segments by timeline
  status
  - Handles AAR blocks and segment gaps
  - Maps segment status to colors: nominal (green), degraded (yellow), critical
    (red)

#### Position Interpolation (Lines 387-425)

- `_interpolate_position_at_time()` - Linear interpolation between waypoints
- Handles International Date Line (IDL) crossing logic
- Used for POI placement and map segment coloring

#### Map Generation (Lines 428-1119)

- `_generate_route_map()` - LARGE function generating 4K PNG (3840x2160 @ 300
  DPI)
  - **Phases 9-12 implementation:**
    - Phase 9: Route line drawing with IDL handling
    - Phase 10: Color-coded segments based on timeline status
    - Phase 11: POI markers (departure, arrival, mission events, satellite
      swaps)
    - Phase 12: Legend inset
  - Uses Cartopy for map projection, Matplotlib for rendering
  - Handles Pacific-centered projections for IDL crossings
  - Bounds calculation with 5% padding
  - Aspect ratio matching for canvas vs geographic bounds
  - Color-coded route segments: nominal/degraded/critical
  - POI integration from route_manager and poi_manager
  - Deployment: Matplotlib in Agg (headless) mode for Docker

#### Timeline Chart (Lines 1122-1284)

- `_generate_timeline_chart()` - Horizontal bar chart (16:5 aspect, 300 DPI PNG)
  - Three transport rows: Ku (StarShield), Ka (CommKa), X-Band
  - State colors: green (AVAILABLE), amber (DEGRADED), red (OFFLINE)
  - T+ time formatting on x-axis
  - 1-hour gridlines

#### DataFrame Builders (Lines 1287-1414)

- `_segment_rows()` - Timeline segments as pandas DataFrame
  - Columns: Segment #, Mission ID/Name, Status, Start/End times, Duration,
    Transport states, Impacted Transports, Reasons, Metadata
  - Combines regular segments with AAR blocks
  - Sorts by start time, then AAR priority

- `_advisory_rows()` - Timeline advisories as DataFrame
  - Columns: Mission ID, UTC/Eastern timestamps, T Offset, Transport, Severity,
    Event Type, Message, Metadata
  - May be empty if no advisories

- `_statistics_rows()` - Mission statistics as DataFrame
  - Humanizes metric names
  - Formats seconds values as HH:MM:SS
  - Filters underscore-prefixed keys

#### Export Format Generators (Lines 1443-2143)

**CSV Export** (Lines 1443-1450)

- Simple wrapper: pandas DataFrame to CSV
- Uses segment_rows() data

**XLSX Export** (Lines 1492-1600)

- Multi-sheet structure:
  1. Summary: Map image (750x500px), Timeline chart (850x300px), Summary table
  2. Timeline: Full segment data
  3. Advisories: Advisory events (if present)
  4. Statistics: Mission metrics (if present)
- Color-coded summary rows: green (NOMINAL), yellow (DEGRADED), red (CRITICAL)
- Column widths optimized for readability
- Images embedded as OpenpyxlImage objects

**PDF Export** (Lines 1603-1869)

- Landscape letter-size pages
- Content: 5. Header with logo (if available), mission name 6. Statistics
  table 7. Route map image (6.5" x 4.3") 8. Transport timeline chart (7" x
  2.3") 9. Timeline segments table (paginated)
- Advanced styling:
  - Status coloring: red for CRITICAL, yellow for DEGRADED/WARNING/SOF
  - Per-column coloring for transport states
  - Safety-of-Flight (SOF) detection from reasons
  - Alternating row backgrounds
  - Font sizing and alignment

**PPTX Export** (Lines 1872-2143)

- Slide 1: Route map (9"W x 6.5"H)
- Slides 2+: Timeline table (paginated, 10 rows/slide, min 3 rows on last slide)
- Pagination logic ensures minimum 3 rows on final slide
- Column widths: [0.6, 1.0, 1.75, 1.75, 1.0, 1.0, 1.0, 1.0, 1.5] weights
- Color-coded rows: red (CRITICAL, 2+ bad systems), yellow
  (DEGRADED/WARNING/SOF), white (nominal)
- SOF detection same as PDF

#### Utility Functions

- `_load_logo_flowable()` - Loads logo image (max 1.6"W x 0.9"H) from assets
- `_base_map_canvas()` - Generates blank 4K map with coastlines/borders/ocean
- `_humanize_metric_name()` - Converts metric keys to display names

#### Main Entry Point (Lines 2173-2220)

- `generate_timeline_export()` - Router function
  - Accepts: format (TimelineExportFormat), mission, timeline,
    parent_mission_id, route_manager, poi_manager
  - Returns: ExportArtifact with content/media_type/extension

### Exporter: Key Dependencies

**External Libraries:**

- matplotlib, cartopy (map visualization)
- PIL (image handling)
- pandas (data manipulation)
- openpyxl (Excel generation)
- reportlab (PDF generation)
- python-pptx (PowerPoint generation)

**Internal Dependencies:**

- app.mission.models (Mission, MissionLegTimeline, TimelineSegment, etc.)
- app.services.poi_manager (POIManager)
- app.services.route_manager (RouteManager)

**Constants:**

- EASTERN_TZ = ZoneInfo("America/New_York")
- STATUS_COLORS = {nominal: green, degraded: yellow, critical: red, unknown:
  gray}
- LOGO_PATH = assets/logo.png
