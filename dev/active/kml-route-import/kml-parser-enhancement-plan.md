# KML Parser Enhancement Plan

## Current Parser Output & Usage
- `parse_kml_file` (`backend/starlink-location/app/services/kml_parser.py`) parses every `<LineString>` and flattens all coordinates into a single ordered list of `RoutePoint` objects, while pulling the document name/description into `RouteMetadata`.
- `RouteManager` (`app/services/route_manager.py`) caches each `ParsedRoute`, exposes metadata to the REST API, and keeps the active route in memory so front-end clients can switch routes instantly.
- The routes API (`app/api/routes.py`) relies on `ParsedRoute.points`, `RouteMetadata`, and helper methods like `get_total_distance()` / `get_bounds()` to serve the route table, detail view, downloads, and statistics used by the UI.
- The GeoJSON/coordinates endpoints (`app/api/geojson.py`) transform `route.points` into the Grafana route layer data; the new `/api/route/coordinates` path expects a clean, monotonically increasing `sequence` field and contiguous coordinates.
- Upcoming Phase 4 work (route-linked POIs) assumes we can associate route metadata with derived POIs, so the parser must remain the source of truth for route geometry while surfacing waypoint information for downstream consumers.

## Observed Structure in `realworld.kml`
- Waypoints and legs are modeled as alternating `<Placemark>` elements: named waypoints with `<Point>` geometry followed by `Placemark` entries literally named `Route` that contain two-point `<LineString>` segments (e.g., `dev/active/kml-route-import/realworld.kml:25-119`).
- Inline `<Style>` blocks on the route segments switch colors (`ffb3b3b3` vs `ffddad05`) to differentiate portions of the flight (primary vs alternates); point placemarks reference shared styles (`#altWaypointIcon`, `#destWaypointIcon`).
- Descriptions embed timing data with leading whitespace/newlines, and some waypoint names contain punctuation (`-TOC-`, `APPCH`, etc.), so naive trimming or parsing will fail.
- The primary departure (`WMSA`) and arrival (`VVNB`) appear twice (start/end), while alternates and approach legs reuse the same icon set—style heuristics alone are insufficient unless combined with ordering and path continuity.
- There is no single continuous `LineString`; reconstructing the route requires stitching many two-point segments in order while ignoring branches that belong to alternate procedures.

## Desired Output Characteristics
- Preserve existing `ParsedRoute` contract: metadata populated from the document, `RoutePoint.sequence` strictly increasing, and coordinates ordered along the primary flight path.
- Exclude alternate legs so downstream consumers (Grafana, REST detail view) see a single continuous trace from departure to primary arrival.
- Surface waypoint/POI candidates (name, coordinates, timing hints) so Phase 4 can create POIs without re-parsing the file.
- Provide informative warnings when the file contains unsupported geometries or when we cannot confidently isolate the main route.

## Implementation Roadmap
1. **Parser Refactor Scaffold**
   - Introduce lightweight internal data classes (e.g., `ParsedPlacemark`, `RouteSegment`, `WaypointNode`) to capture raw placemark information before committing to the final `ParsedRoute`.
   - Normalize whitespace, namespace handling, and style references during ingestion.

2. **Waypoint Classification**
   - Classify point placemarks using a combination of style URL, document position, and name matching to identify departure, arrival, alternates, and intermediate fixes.
   - Record timing metadata from descriptions for potential POI enrichment, but keep parsing tolerant of missing or malformed timestamps.

3. **Segment Assembly**
   - Order `Route` segments by document appearance, capture start/end coordinates, and associate them with nearby waypoint nodes (matching shared coordinates within a tolerance).
   - Merge consecutive legs that share endpoints to build candidate chains; deduplicate repeated coordinates while preserving sequence.

4. **Primary Path Selection**
   - Choose the chain that starts at the departure waypoint and terminates at the primary arrival, preferring legs that maintain consistent styling (gold segments in sample) and maximizing total distance/point count.
   - Detect and drop side branches (alternates/approaches) by identifying chains that diverge from the main path or loop back without reaching the arrival field.

5. **RoutePoint Emission**
   - Flatten the primary chain into `RoutePoint` instances with sequential numbering, carrying altitude values when present (default to `None` otherwise).
   - Populate `RouteMetadata` with document name/description and accurate `point_count`.

6. **POI Extraction Hook**
   - Return (or stage for later phases) a structured list of waypoint placemarks linked to the chosen route so POI creation can happen without re-reading the XML.
   - Ensure cascade deletion requirements are supported by including a route identifier reference.

7. **Error Handling & Logging**
   - Log detailed diagnostics when segments fail to match waypoints, when multiple plausible primary chains exist, or when the parser falls back to legacy behavior (all segments concatenated).
   - Surface actionable messages through `KMLParseError` so the UI can display clear import failures.

## Validation & Tooling
- Add unit tests that feed the sample `realworld.kml` through the parser and assert the output path starts at WMSA, ends at VVNB, and omits alternate loops.
- Create synthetic fixtures covering edge cases: missing styles, single multi-coordinate `LineString`, altitude-inclusive coordinates, and malformed descriptions.
- Verify downstream integrations by smoke-testing `/api/routes`, `/api/route/coordinates`, and Grafana dashboards with the new output to ensure sequence ordering and metadata remain intact.

## Open Questions / Follow-Ups
- Confirm whether we should expose alternate legs as optional overlays (future enhancement) or discard them entirely for now.
- Decide where to persist waypoint/POI extraction results (immediate return value vs. separate service) before Phase 4 implementation.
- Determine acceptable heuristics when departure/arrival icons are ambiguous—do we fall back to first/last waypoint or reject the file?
