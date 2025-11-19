# Checklist for excel-sheet1-timeline-summary (Map Reset)

**Branch:** `feat/excel-sheet1-timeline-summary`
**Folder:** `dev/active/excel-sheet1-timeline-summary/`
**Status:** Phase 7 Map Reset - In Progress
**Skill:** executing-plan-checklist

> This checklist is intentionally extremely detailed and assumes the executor
> has no prior knowledge of the repo or codebase. Every step must be followed
> exactly, in order, without combining or skipping.

---

## Context: What We're Doing

The existing map output has a broken aspect ratio (1280x1024 too wide/short) and the legend takes up 40% of the figure space. We are completely resetting the map generation logic to output proper 4K resolution (3840x2880 pixels @ 300 DPI) with smart 5% padding and proper legend placement.

**Important:** Each phase below has a STOP point where you must test the output before proceeding to the next phase. Do not skip testing steps.

---

## Phase 7: Map Reset - Base 4K Canvas

### 7.1: Locate the current _generate_route_map function

- [x] Open file: `backend/starlink-location/app/mission/exporter.py`
- [x] Find the function `_generate_route_map` (starts at line 290)
- [x] Verify it ends around line 550 (look for the next function definition `def _generate_timeline_chart`)
- [x] Note: This function will be completely rewritten

### 7.2: Replace _generate_route_map with base 4K canvas implementation

- [x] In `backend/starlink-location/app/mission/exporter.py`, replace the entire `_generate_route_map()` function (lines 290-550) with:

```python
def _generate_route_map(timeline: MissionTimeline, mission: Mission | None = None) -> bytes:
    """Generate a 4K PNG image of the route map.

    Current phase: Base canvas only (Phase 7)
    - Output: 3840x2880 pixels @ 300 DPI
    - No route drawn yet, no POIs, no text overlays

    Args:
        timeline: The mission timeline with segments and timing data
        mission: The mission object containing route and POI information (optional)

    Returns:
        PNG image as bytes.
    """
    # Phase 7: Base 4K canvas with no content
    # Resolution: 3840 x 2880 pixels at 300 DPI
    # This equals 12.8" x 9.6" at 300 DPI (standard for print)

    # Calculate figure size: figsize in inches = pixels / dpi
    width_inches = 3840 / 300  # 12.8 inches
    height_inches = 2880 / 300  # 9.6 inches

    fig = plt.figure(figsize=(width_inches, height_inches), dpi=300, facecolor='white')
    ax = fig.add_subplot(111, projection=ccrs.PlateCarree())

    # Remove all padding, margins, and borders
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # Set a default extent (will be overridden in Phase 8)
    ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())

    # Add basic map features
    ax.coastlines(resolution='50m', linewidth=0.5, color='#2c3e50')
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, color='#bdc3c7')
    ax.add_feature(cfeature.LAND, facecolor='#ecf0f1', edgecolor='none')
    ax.add_feature(cfeature.OCEAN, facecolor='#d5e8f7', edgecolor='none')

    # Subtle gridlines without labels
    ax.gridlines(draw_labels=False, alpha=0.1, linestyle='-', linewidth=0.3, color='#95a5a6')

    # Remove axis ticks and spines for clean, borderless appearance
    ax.spines['geo'].set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])

    # Save to PNG bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
```

- [x] Save the file
- [x] Expected result: File saved without errors

### 7.3: Rebuild Docker environment

- [x] In terminal, run:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Expected result: Build completes without errors, all containers start healthy
- [x] Note: This will take 2-5 minutes

### 7.4: Verify backend health

- [x] Run:
  ```bash
  curl http://localhost:8000/health
  ```
- [x] Expected result: JSON response with `"status": "ok"`

### 7.5: Generate test export to verify Phase 7 output

- [x] Use API to generate an Excel export (you'll need an existing mission ID):
  ```bash
  curl -o /tmp/test_map_phase7.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```
  - Replace `{MISSION_ID}` with an actual mission ID from your database
  - If you don't have one, you may need to create a test mission first
- [x] Expected result: File `/tmp/test_map_phase7.xlsx` is created

### 7.6: Manually verify Phase 7 canvas output

- [x] Open the exported Excel file in Excel or LibreOffice Calc
- [x] Go to the "Summary" sheet (should be first sheet)
- [x] Look at the map image at the top
- [x] Verify visually:
  - [x] Map shows world with coastlines and oceans (blue water, light gray land)
  - [x] Map has proper 4K aspect ratio (should look like a wider, taller image than before)
  - [x] No route drawn on map (just empty world map)
  - [x] No POI markers
  - [x] No legend
  - [x] Clean borderless appearance with no axis labels
- [x] **STOP HERE**: Once you confirm the base canvas looks correct with proper dimensions, proceed to Phase 8

### 7.7: Commit Phase 7 changes

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: reset map to base 4K canvas (Phase 7)"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 8: Map - Calculate & Display Route Bounds

### 8.1: Add route waypoint extraction and bounds calculation

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Find the `_generate_route_map()` function
- [x] Replace the function body (after the docstring, replace the `fig = plt.figure(...)` section onwards) with:

```python
    # Phase 8: Calculate map bounds from route with smart 5% padding

    # Check if we have valid mission and route data
    if mission is None or not mission.route_id or not _route_manager:
        # Return base canvas if no mission data
        width_inches = 3840 / 300
        height_inches = 2880 / 300
        fig = plt.figure(figsize=(width_inches, height_inches), dpi=300, facecolor='white')
        ax = fig.add_subplot(111, projection=ccrs.PlateCarree())
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())
        ax.coastlines(resolution='50m', linewidth=0.5, color='#2c3e50')
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, color='#bdc3c7')
        ax.add_feature(cfeature.LAND, facecolor='#ecf0f1', edgecolor='none')
        ax.add_feature(cfeature.OCEAN, facecolor='#d5e8f7', edgecolor='none')
        ax.gridlines(draw_labels=False, alpha=0.1, linestyle='-', linewidth=0.3, color='#95a5a6')
        ax.spines['geo'].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # Fetch route from manager
    route = _route_manager.get_route(mission.route_id)
    if route is None or not route.points:
        # Return base canvas if route not found
        width_inches = 3840 / 300
        height_inches = 2880 / 300
        fig = plt.figure(figsize=(width_inches, height_inches), dpi=300, facecolor='white')
        ax = fig.add_subplot(111, projection=ccrs.PlateCarree())
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())
        ax.coastlines(resolution='50m', linewidth=0.5, color='#2c3e50')
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, color='#bdc3c7')
        ax.add_feature(cfeature.LAND, facecolor='#ecf0f1', edgecolor='none')
        ax.add_feature(cfeature.OCEAN, facecolor='#d5e8f7', edgecolor='none')
        ax.gridlines(draw_labels=False, alpha=0.1, linestyle='-', linewidth=0.3, color='#95a5a6')
        ax.spines['geo'].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # Extract waypoint coordinates
    points = route.points
    lats = [p.latitude for p in points]
    lons = [p.longitude for p in points]

    if not lats or not lons:
        # Return base canvas if no valid waypoints
        width_inches = 3840 / 300
        height_inches = 2880 / 300
        fig = plt.figure(figsize=(width_inches, height_inches), dpi=300, facecolor='white')
        ax = fig.add_subplot(111, projection=ccrs.PlateCarree())
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())
        ax.coastlines(resolution='50m', linewidth=0.5, color='#2c3e50')
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, color='#bdc3c7')
        ax.add_feature(cfeature.LAND, facecolor='#ecf0f1', edgecolor='none')
        ax.add_feature(cfeature.OCEAN, facecolor='#d5e8f7', edgecolor='none')
        ax.gridlines(draw_labels=False, alpha=0.1, linestyle='-', linewidth=0.3, color='#95a5a6')
        ax.spines['geo'].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # Detect IDL (International Date Line) crossings
    idl_crossing_segments = set()
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i + 1]
        lon_diff = abs(p2.longitude - p1.longitude)
        if lon_diff > 180:
            idl_crossing_segments.add(i)

    # Use only valid waypoints (excluding IDL-crossing segments) for bounds calculation
    valid_indices = [i for i in range(len(points))
                     if i not in idl_crossing_segments and (i == 0 or i - 1 not in idl_crossing_segments)]

    if valid_indices:
        valid_lats = [points[i].latitude for i in valid_indices]
        valid_lons = [points[i].longitude for i in valid_indices]
        min_lat, max_lat = min(valid_lats), max(valid_lats)
        min_lon, max_lon = min(valid_lons), max(valid_lons)
    else:
        # Fallback if all segments cross IDL (shouldn't happen)
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

    # Calculate route extent
    lat_range = max_lat - min_lat if max_lat != min_lat else 1.0
    lon_range = max_lon - min_lon if max_lon != min_lon else 1.0

    # Smart 5% padding: apply padding to the larger dimension, adjust other for aspect ratio
    if lon_range >= lat_range:
        # East-West dominant: 5% padding on E/W, height adjusts
        padding_lon = lon_range * 0.05
        bounds_west = min_lon - padding_lon
        bounds_east = max_lon + padding_lon

        # Calculate padded longitude range
        padded_lon_range = bounds_east - bounds_west

        # Aspect ratio of 4K canvas: 3840/2880 = 4:3 = 1.333
        # At equator: degrees_lat = degrees_lon * (canvas_height / canvas_width)
        target_lat_range = padded_lon_range * (2880 / 3840)

        # Center latitude bounds on route center
        lat_center = (min_lat + max_lat) / 2
        bounds_south = lat_center - (target_lat_range / 2)
        bounds_north = lat_center + (target_lat_range / 2)
    else:
        # North-South dominant: 5% padding on N/S, width adjusts
        padding_lat = lat_range * 0.05
        bounds_south = min_lat - padding_lat
        bounds_north = max_lat + padding_lat

        # Calculate padded latitude range
        padded_lat_range = bounds_north - bounds_south

        # Aspect ratio: degrees_lon = degrees_lat * (canvas_width / canvas_height)
        target_lon_range = padded_lat_range * (3840 / 2880)

        # Center longitude bounds on route center
        lon_center = (min_lon + max_lon) / 2
        bounds_west = lon_center - (target_lon_range / 2)
        bounds_east = lon_center + (target_lon_range / 2)

    # Create 4K figure
    width_inches = 3840 / 300
    height_inches = 2880 / 300

    fig = plt.figure(figsize=(width_inches, height_inches), dpi=300, facecolor='white')
    ax = fig.add_subplot(111, projection=ccrs.PlateCarree())

    # Remove all padding and margins
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # Set map extent to calculated bounds
    ax.set_extent([bounds_west, bounds_east, bounds_south, bounds_north],
                  crs=ccrs.PlateCarree())

    # Add map features
    ax.coastlines(resolution='50m', linewidth=0.5, color='#2c3e50')
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, color='#bdc3c7')
    ax.add_feature(cfeature.LAND, facecolor='#ecf0f1', edgecolor='none')
    ax.add_feature(cfeature.OCEAN, facecolor='#d5e8f7', edgecolor='none')

    # Subtle gridlines without labels
    ax.gridlines(draw_labels=False, alpha=0.1, linestyle='-', linewidth=0.3, color='#95a5a6')

    # Remove axis ticks and spines for clean appearance
    ax.spines['geo'].set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])

    # Save to PNG bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
```

- [x] Save the file

### 8.2: Rebuild Docker and verify

- [x] Run:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Verify health:
  ```bash
  curl http://localhost:8000/health
  ```

### 8.3: Generate test export for Phase 8

- [x] Use same mission ID as Phase 7:
  ```bash
  curl -o /tmp/test_map_phase8.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```

### 8.4: Manually verify Phase 8 bounds output

- [x] Open `/tmp/test_map_phase8.xlsx` in Excel or LibreOffice
- [x] Go to Summary sheet, look at the map image
- [x] Verify visually:
  - [x] Map now shows only the area around the route (zoomed in from world map)
  - [x] Route extent is visible with appropriate padding around it
  - [x] If route is primarily E-W: padding appears on east and west, latitude auto-adjusted
  - [x] If route is primarily N-S: padding appears on north and south, longitude auto-adjusted
  - [x] Aspect ratio still correct (4K: 3840x2880)
  - [x] No route line drawn yet (still just terrain)
- [x] **STOP HERE**: Once you confirm bounds are correct, proceed to Phase 9

### 8.5: Commit Phase 8 changes

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: add route bounds calculation with smart 5% padding (Phase 8)"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 9: Map - Draw Route as Simple Line

### 9.1: Add route line drawing to _generate_route_map

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Find the `_generate_route_map()` function
- [x] Before the final `buf = io.BytesIO()` and `plt.savefig(...)` section, add:

```python
    # Phase 9: Draw route as single-color line
    # Draw route as simple connected line (no color coding yet)
    if points:
        # Filter out IDL-crossing segments
        route_lons = []
        route_lats = []
        current_segment = []

        for i in range(len(points)):
            current_segment.append((points[i].longitude, points[i].latitude))

            # If next segment would cross IDL, draw current segment and start new one
            if i < len(points) - 1 and i in idl_crossing_segments:
                if len(current_segment) > 1:
                    seg_lons = [p[0] for p in current_segment]
                    seg_lats = [p[1] for p in current_segment]
                    ax.plot(seg_lons, seg_lats, color='#2c3e50', linewidth=2,
                           transform=ccrs.PlateCarree(), zorder=5)
                current_segment = []

        # Draw final segment
        if len(current_segment) > 1:
            seg_lons = [p[0] for p in current_segment]
            seg_lats = [p[1] for p in current_segment]
            ax.plot(seg_lons, seg_lats, color='#2c3e50', linewidth=2,
                   transform=ccrs.PlateCarree(), zorder=5)
```

- [x] Save the file

### 9.2: Rebuild Docker and verify

- [x] Run:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Verify health:
  ```bash
  curl http://localhost:8000/health
  ```

### 9.3: Generate test export for Phase 9

- [x] Use same mission ID:
  ```bash
  curl -o /tmp/test_map_phase9.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```

### 9.4: Manually verify Phase 9 route line output

- [x] Open `/tmp/test_map_phase9.xlsx`
- [x] Go to Summary sheet, look at the map
- [x] Verify visually:
  - [x] Single dark blue/gray line is drawn on the map showing the route
  - [x] Line follows the expected geographic path (matches your knowledge of the mission route)
  - [x] Line does not have IDL artifacts (no diagonal lines crossing the map)
  - [x] Entire route is visible within the map bounds
  - [x] Line is visible but not overwhelming (appropriate width)
- [x] **STOP HERE**: Once route geometry looks correct, proceed to Phase 10

### 9.5: Commit Phase 9 changes

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: draw route as simple line (Phase 9)"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 10: Map - Add Color-Coded Segments

### 10.1: Replace route drawing with color-coded segments

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Find the route drawing section you added in Phase 9 (the code starting with `if points:`)
- [x] Replace that section with:

```python
    # Phase 10: Draw route with color-coded segments by status
    status_colors = {
        "NOMINAL": "#27ae60",      # Modern emerald green
        "DEGRADED": "#f39c12",     # Modern amber/orange
        "CRITICAL": "#e74c3c",     # Modern red
    }

    if points and timeline.segments:
        # Calculate mission duration for time-based waypoint interpolation
        mission_start = _ensure_timezone(timeline.segments[0].start_time)
        mission_end = _ensure_timezone(timeline.segments[-1].end_time)
        total_duration_sec = (mission_end - mission_start).total_seconds()

        # For each route segment (between consecutive waypoints), determine its color
        for i in range(len(points) - 1):
            # Skip segments that cross IDL
            if i in idl_crossing_segments:
                continue

            p1 = points[i]
            p2 = points[i + 1]

            # Calculate time at the midpoint of this route segment
            # Assume waypoints are evenly distributed along the route
            segment_progress = i / len(points)
            segment_time = mission_start + (mission_end - mission_start) * segment_progress

            # Find which timeline segment contains this time
            segment_status = "NOMINAL"  # Default
            for tl_seg in timeline.segments:
                if tl_seg.start_time <= segment_time <= tl_seg.end_time:
                    segment_status = tl_seg.status.name
                    break

            # Get color for this status
            color = status_colors.get(segment_status, "#95a5a6")  # Gray fallback

            # Draw this route segment
            ax.plot([p1.longitude, p2.longitude],
                   [p1.latitude, p2.latitude],
                   color=color, linewidth=2,
                   transform=ccrs.PlateCarree(), zorder=5)
```

- [x] Save the file

### 10.2: Rebuild Docker and verify

- [x] Run:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Verify health:
  ```bash
  curl http://localhost:8000/health
  ```

### 10.3: Generate test export for Phase 10

- [x] Use same mission ID:
  ```bash
  curl -o /tmp/test_map_phase10.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```

### 10.4: Manually verify Phase 10 color-coded route output

- [x] Open `/tmp/test_map_phase10.xlsx`
- [x] Go to Summary sheet, look at the map
- [x] Verify visually:
  - [x] Route is drawn with multiple colors
  - [x] Green segments appear where timeline status is NOMINAL
  - [x] Yellow/amber segments appear where timeline status is DEGRADED
  - [x] Red segments appear where timeline status is CRITICAL
  - [x] Compare colors with Timeline sheet: segment colors should match status column
  - [x] No IDL artifacts
  - [x] Route is fully visible within bounds
- [x] **STOP HERE**: Once color coding matches timeline data, proceed to Phase 11

### 10.5: Commit Phase 10 changes

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: add color-coded route segments by timeline status (Phase 10)"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 11: Map - Add POI & Airport Markers

### 11.1: Add departure, arrival, and POI markers

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Before the final `buf = io.BytesIO()` section, add:

```python
    # Phase 11: Add POI and airport markers

    # Departure airport marker (at first waypoint)
    if points:
        dep_lon = points[0].longitude
        dep_lat = points[0].latitude
        ax.plot(dep_lon, dep_lat, marker='^', color='#3498db', markersize=12,
               transform=ccrs.PlateCarree(), zorder=10)
        ax.text(dep_lon, dep_lat, '  Departure', fontsize=9, color='#3498db',
               transform=ccrs.PlateCarree(), zorder=11,
               verticalalignment='bottom', horizontalalignment='left',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none'))

    # Arrival airport marker (at last waypoint)
    if points:
        arr_lon = points[-1].longitude
        arr_lat = points[-1].latitude
        ax.plot(arr_lon, arr_lat, marker='v', color='#9b59b6', markersize=12,
               transform=ccrs.PlateCarree(), zorder=10)
        ax.text(arr_lon, arr_lat, '  Arrival', fontsize=9, color='#9b59b6',
               transform=ccrs.PlateCarree(), zorder=11,
               verticalalignment='top', horizontalalignment='left',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none'))

    # Mission-event POI markers
    if mission.pois:
        for poi in mission.pois:
            if poi.poi_type == 'mission-event':
                ax.plot(poi.longitude, poi.latitude, marker='o', color='#e67e22', markersize=10,
                       transform=ccrs.PlateCarree(), zorder=10)
                ax.text(poi.longitude, poi.latitude, f'  {poi.name}', fontsize=8, color='#e67e22',
                       transform=ccrs.PlateCarree(), zorder=11,
                       verticalalignment='center', horizontalalignment='left',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='none'))
```

- [x] Save the file

### 11.2: Rebuild Docker and verify

- [x] Run:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Verify health:
  ```bash
  curl http://localhost:8000/health
  ```

### 11.3: Generate test export for Phase 11

- [x] Use same mission ID:
  ```bash
  curl -o /tmp/test_map_phase11.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```

### 11.4: Manually verify Phase 11 markers output

- [x] Open `/tmp/test_map_phase11.xlsx`
- [x] Go to Summary sheet, look at the map
- [x] Verify visually:
  - [x] Blue triangle marker appears at route start, labeled "Departure"
  - [x] Purple triangle marker appears at route end, labeled "Arrival"
  - [x] Orange circle markers appear at mission-event POIs
  - [x] All POI markers are labeled with POI names
  - [x] Labels are readable and positioned clearly
  - [x] Markers do not obscure the route line
  - [x] All expected POIs are present (compare with mission data)
- [x] **STOP HERE**: Once all markers are correct, proceed to Phase 12

### 11.5: Commit Phase 11 changes

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: add POI and airport markers with labels (Phase 11)"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 12: Map - Add Legend Inset

### 12.1: Add legend to map

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Before the final `buf = io.BytesIO()` section, add:

```python
    # Phase 12: Add legend inset to map
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    legend_elements = [
        # Route status colors
        Line2D([0], [0], color='#27ae60', linewidth=3, label='Nominal'),
        Line2D([0], [0], color='#f39c12', linewidth=3, label='Degraded'),
        Line2D([0], [0], color='#e74c3c', linewidth=3, label='Critical'),
        # Marker types
        Line2D([0], [0], marker='^', color='w', markerfacecolor='#3498db',
               markersize=8, label='Departure', linestyle='None'),
        Line2D([0], [0], marker='v', color='w', markerfacecolor='#9b59b6',
               markersize=8, label='Arrival', linestyle='None'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#e67e22',
               markersize=8, label='POI', linestyle='None'),
    ]

    # Add legend inset at lower-right, positioned to not extend beyond figure
    legend = ax.legend(handles=legend_elements, loc='lower right', fontsize=9,
                      framealpha=0.95, edgecolor='#2c3e50', fancybox=True)
    # Ensure legend is drawn on top and doesn't extend beyond axes
    legend.set_zorder(100)
```

- [x] Save the file

### 12.2: Rebuild Docker and verify

- [x] Run:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Verify health:
  ```bash
  curl http://localhost:8000/health
  ```

### 12.3: Generate test export for Phase 12

- [x] Use same mission ID:
  ```bash
  curl -o /tmp/test_map_phase12.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```

### 12.4: Manually verify Phase 12 legend output

- [x] Open `/tmp/test_map_phase12.xlsx`
- [x] Go to Summary sheet, look at the map
- [x] Verify visually:
  - [x] Legend appears in lower-right corner of map
  - [x] Legend shows: Nominal (green), Degraded (orange), Critical (red)
  - [x] Legend shows: Departure (blue triangle), Arrival (purple triangle), POI (orange circle)
  - [x] Legend text is readable
  - [x] Legend does NOT extend beyond the map figure boundaries
  - [x] Legend does not obscure important map features
  - [x] Legend has proper spacing and formatting
- [x] **STOP HERE**: Once legend looks good, proceed to Phase 13

### 12.5: Commit Phase 12 changes

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: add legend inset to map (Phase 12)"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 13: Full Integration & Testing

### 13.1: Verify map integrates with timeline chart and summary table

- [x] Use same mission ID from testing:
  ```bash
  curl -o /tmp/test_integration.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```

### 13.2: Verify Excel Sheet 1 (Summary) layout

- [x] Open `/tmp/test_integration.xlsx`
- [x] Go to "Summary" sheet (should be first sheet)
- [x] Verify order and layout:
  - [x] Map image appears at top
  - [x] Timeline chart appears below map
  - [x] Summary table appears below chart
  - [x] All three elements fit on the sheet properly
  - [x] Column widths are reasonable

### 13.3: Verify Timeline sheet is unchanged

- [x] Go to "Timeline" sheet
- [x] Verify:
  - [x] All original columns present (13 columns total)
  - [x] Data looks correct
  - [x] No formatting changes

### 13.4: Verify Statistics sheet is unchanged

- [x] Go to "Statistics" sheet
- [x] Verify:
  - [x] Original content present
  - [x] Data looks correct

### 13.5: Verify PDF export includes map and chart

- [x] Generate PDF export:
  ```bash
  curl -o /tmp/test_integration.pdf http://localhost:8000/api/missions/{MISSION_ID}/export/pdf
  ```
- [x] Open `/tmp/test_integration.pdf` in PDF viewer
- [x] Verify:
  - [x] PDF has multiple pages
  - [x] Map image appears on a page
  - [x] Timeline chart appears on a page
  - [x] Chart matches the Excel version
  - [x] All pages render correctly

### 13.6: Check backend logs for errors

- [x] Run:
  ```bash
  docker compose logs starlink-location | rg -i "error|exception" | head -20
  ```
- [x] Expected result: No export-related errors
- [x] If errors appear, note them and address in code before proceeding

### 13.7: Commit integration verification

- [x] If no code changes needed:
  ```bash
  git status
  ```
- [x] Expected result: "nothing to commit, working tree clean"
- [x] If code changes were made during testing, commit them:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  git commit -m "test: verify full integration of map, chart, and summary table"
  git push
  ```

---

## Phase 14: Documentation & Wrap-Up

### 14.1: Update MISSION-PLANNING-GUIDE.md with map specifications

- [x] Open `docs/MISSION-PLANNING-GUIDE.md`
- [x] Find the section describing Excel exports (look for "Sheet 1")
- [x] Update the Sheet 1 description to include map specifications:
  ```markdown
  **Sheet 1: Summary**
  - Geographic map showing mission route with color-coded segments (green=NOMINAL, yellow=DEGRADED, red=CRITICAL)
  - Map resolution: 3840×2880 pixels @ 300 DPI (12.8" × 9.6" for printing)
  - Labeled markers for departure airport (blue), arrival airport (purple), and mission-event POIs (orange)
  - Route centered with 5% smart padding (5% on larger dimension, other dimension auto-adjusted for aspect ratio)
  - Horizontal timeline bar chart showing X-Band, Ka, and Ku transport states over time
  - Simplified summary table with columns: Start (UTC), Duration, Status, Systems Down
  - Color-coded table rows matching segment status
  ```
- [x] Save the file

### 14.2: Update PLAN.md status

- [x] Open `dev/active/excel-sheet1-timeline-summary/PLAN.md`
- [x] Change the line:
  ```
  **Status:** Phase 7 (Testing & Verification - In Progress)
  ```
  to:
  ```
  **Status:** Completed
  ```
- [x] Save the file

### 14.3: Update CONTEXT.md

- [x] Open `dev/active/excel-sheet1-timeline-summary/CONTEXT.md`
- [x] Update the "Last Updated" field to today's date
- [x] Review all sections for accuracy
- [x] If any new findings or constraints were discovered, add them
- [x] Save the file

### 14.4: Mark all checklist items complete

- [x] Review this entire checklist
- [x] Ensure all `- [x]` items are marked `- [x]`
- [x] Save the file

### 14.5: Commit final documentation

- [x] Stage all documentation changes:
  ```bash
  git add docs/MISSION-PLANNING-GUIDE.md
  git add dev/active/excel-sheet1-timeline-summary/PLAN.md
  git add dev/active/excel-sheet1-timeline-summary/CONTEXT.md
  git add dev/active/excel-sheet1-timeline-summary/CHECKLIST.md
  ```
- [x] Commit:
  ```bash
  git commit -m "docs: update documentation for map reset completion"
  ```
- [x] Push:
  ```bash
  git push
  ```

### 14.6: Verify all changes are committed and pushed

- [x] Run:
  ```bash
  git status
  ```
- [x] Expected result: "nothing to commit, working tree clean"

### 14.7: Ready for wrap-up skill

- [x] This feature is complete
- [x] All checklist items are marked as done
- [x] All changes are committed and pushed
- [x] Use the `wrapping-up-plan` skill to create the PR

---

## Phase 15: Code Review Feedback & Quality Improvements

### 15.1: Fix color code inconsistency

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Find the `STATUS_COLORS` dictionary (around line 556)
- [x] Find the `legend_elements` creation (around line 1053)
- [x] Verify the hex codes match exactly between the two:
  - GREEN (NOMINAL): Both should use same color (currently `#27ae60`)
  - ORANGE (DEGRADED): Both should use same color (currently `#f39c12`)
  - RED (CRITICAL): Both should use same color (currently `#e74c3c`)
- [x] If they differ, update `legend_elements` to match `STATUS_COLORS`
- [x] Save the file

### 15.2: Add error logging to Excel map embedding

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Find the Excel map embedding section (around line 1440-1460)
- [x] Replace bare `pass` statement with:
  ```python
  except Exception as e:
      logger.error("Failed to embed map image in Excel: %s", e, exc_info=True)
  ```
- [x] Save the file

### 15.3: Add error logging to Excel chart embedding

- [x] In the same file, find the chart embedding section (around line 1460-1480)
- [x] Replace bare `pass` statement with:
  ```python
  except Exception as e:
      logger.error("Failed to embed timeline chart in Excel: %s", e, exc_info=True)
  ```
- [x] Save the file

### 15.4: Add error logging to PDF map generation

- [x] Find the PDF map generation section (around line 1560-1575)
- [x] Replace the broad exception handler with:
  ```python
  except Exception as e:
      logger.error("Failed to generate route map for PDF: %s", e, exc_info=True)
      story.append(Paragraph(f"[Route map unavailable: {str(e)}]", styles["Normal"]))
  ```
- [x] Save the file

### 15.5: Add error logging to PDF chart generation

- [x] Find the PDF chart generation section (around line 1580-1600)
- [x] Replace the broad exception handler with:
  ```python
  except Exception as e:
      logger.error("Failed to generate timeline chart for PDF: %s", e, exc_info=True)
      story.append(Paragraph(f"[Timeline chart unavailable: {str(e)}]", styles["Normal"]))
  ```
- [x] Save the file

### 15.6: Move logger initialization to module level

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Check the imports at the top of the file (around line 1-50)
- [x] Find any `logging` module import
- [x] If not present, add it after other imports:
  ```python
  import logging
  ```
- [x] After imports, add module-level logger initialization (after line ~50):
  ```python
  logger = logging.getLogger(__name__)
  ```
- [x] Find the `_generate_route_map()` function (around line 376)
- [x] If it contains `import logging` or `logger = logging.getLogger(...)`, remove those lines from inside the function
- [x] Save the file

### 15.7: Refactor duplicate base map canvas code

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Find the `_generate_route_map()` function
- [x] Identify the base map canvas generation code (appears 3+ times for different early-return conditions)
- [x] Extract this into a helper function at the end of the file:
  ```python
  def _base_map_canvas() -> bytes:
      """Generate a blank 4K map canvas with no route or markers."""
      width_inches = 3840 / 300
      height_inches = 2880 / 300

      fig = plt.figure(figsize=(width_inches, height_inches), dpi=300, facecolor='white')
      ax = fig.add_subplot(111, projection=ccrs.PlateCarree())
      fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
      ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())
      ax.coastlines(resolution='50m', linewidth=0.5, color='#2c3e50')
      ax.add_feature(cfeature.BORDERS, linewidth=0.5, color='#bdc3c7')
      ax.add_feature(cfeature.LAND, facecolor='#ecf0f1', edgecolor='none')
      ax.add_feature(cfeature.OCEAN, facecolor='#d5e8f7', edgecolor='none')
      ax.gridlines(draw_labels=False, alpha=0.1, linestyle='-', linewidth=0.3, color='#95a5a6')
      ax.spines['geo'].set_visible(False)
      ax.set_xticks([])
      ax.set_yticks([])

      buf = io.BytesIO()
      plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0)
      plt.close(fig)
      buf.seek(0)
      return buf.read()
  ```
- [x] Replace the 3+ duplicate blocks with calls to `return _base_map_canvas()`
- [x] Save the file

### 15.8: Refactor IDL crossing logic in geojson.py

- [x] Open `backend/starlink-location/app/api/geojson.py`
- [x] Find the International Date Line crossing handling section (around line 140-230)
- [x] Identify the repeated blocks for appending interpolated points
- [x] Refactor to extract `lon_to_add` logic:
  - Move the `lon_to_add = None` initialization outside the repeated block
  - Determine `lon_to_add` based on hemisphere and direction once
  - Use single `if lon_to_add is not None:` block to append to coordinates
- [x] Remove duplicate append statements
- [x] Add comments to clarify the logic
- [x] Save the file

### 15.9: Clean up commented exploration code in exporter.py

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Find the large IDL crossing block in `_generate_route_map()` (around line 851)
- [x] Review all commented-out code and exploration notes
- [x] Remove all commented lines (keep only active code)
- [x] Keep one clear comment explaining the IDL crossing handling approach
- [x] Save the file

### 15.10: Optimize Docker layers

- [x] Open `backend/starlink-location/Dockerfile`
- [x] Find the section with multiple consecutive `RUN` commands (around line 41)
- [x] Combine all mkdir and chown operations into a single `RUN` command:
  ```dockerfile
  RUN mkdir -p /data/routes /data/sim_routes /home/appuser/.local/share/cartopy /home/appuser/.config/matplotlib /home/appuser/.cache/matplotlib && \
      chown -R appuser:appuser /data /home/appuser/.local /home/appuser/.config /home/appuser/.cache && \
      chmod -R 755 /data /home/appuser/.local /home/appuser/.config /home/appuser/.cache
  ```
- [x] Save the file

### 15.11: Remove redundant coordinates initialization in geojson.py

- [x] Open `backend/starlink-location/app/api/geojson.py`
- [x] Find line 141 where `coordinates` is first initialized
- [x] Find the second initialization of `coordinates` (should be a few lines later)
- [x] Keep only the second initialization (the one with the comment "Convert route points...")
- [x] Remove the first duplicate initialization
- [x] Save the file

### 15.12: Rebuild Docker and test

- [x] Run Docker rebuild:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Verify health:
  ```bash
  curl http://localhost:8000/health
  ```
- [x] Expected result: `{"status": "ok", ...}`

### 15.13: Verify no functionality changes

- [x] Generate test export with same mission ID as before:
  ```bash
  curl -o /tmp/test_after_refactor.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```
- [x] Open file in Excel/LibreOffice
- [x] Verify visually:
  - Map still renders correctly with same layout
  - Colors still match (green/orange/red segments match timeline)
  - Chart still displays correctly
  - Summary table unchanged
- [x] Check backend logs for new error logging:
  ```bash
  docker compose logs starlink-location | rg "error|Failed" | head -5
  ```
- [x] Expected result: No export-related errors (healthy start/shutdown logs only)

### 15.14: Commit all quality improvements

- [x] Stage all changed files:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  git add backend/starlink-location/app/api/geojson.py
  git add backend/starlink-location/Dockerfile
  ```
- [x] Commit:
  ```bash
  git commit -m "refactor: address code review feedback - improve quality and maintainability

- Consolidate color codes into single constant (fixes HIGH priority issue)
- Add error logging to Excel/PDF image embedding (fixes HIGH priority issue)
- Extract duplicate base map canvas code to helper function
- Refactor IDL crossing logic to reduce duplication in geojson.py
- Move logger initialization to module level
- Remove commented exploration code from _generate_route_map()
- Optimize Docker layers by combining RUN commands
- Remove redundant coordinates initialization in geojson.py"
  ```
- [x] Push:
  ```bash
  git push
  ```

### 15.15: Update CHECKLIST.md

- [x] Mark all Phase 15 items as complete: `- [x]`
- [x] Save the file

### 15.16: Commit plan documentation

- [x] Stage changes:
  ```bash
  git add dev/active/excel-sheet1-timeline-summary/PLAN.md
  git add dev/active/excel-sheet1-timeline-summary/CHECKLIST.md
  ```
- [x] Commit:
  ```bash
  git commit -m "chore: document Phase 15 code review feedback improvements"
  ```
- [x] Push:
  ```bash
  git push
  ```

### 15.17: Verify PR ready for merge

- [x] View updated PR:
  ```bash
  gh pr view 10
  ```
- [x] Expected result: All code review comments should be addressed by commits
- [x] All tests passing
- [x] Ready for merge

---

## Testing Summary

The following were tested during this implementation:

- [x] Phase 7: Base 4K canvas generates with correct dimensions
- [x] Phase 8: Route bounds calculated correctly with smart 5% padding
- [x] Phase 9: Route drawn as single line with correct geometry
- [x] Phase 10: Route segments colored correctly by timeline status
- [x] Phase 11: Departure, arrival, and POI markers all present and labeled
- [x] Phase 12: Legend positioned correctly and does not extend boundaries
- [x] Phase 13: Full integration with timeline chart and summary table working
- [x] Phase 13: PDF export includes map and chart correctly
- [x] Phase 13: No errors in backend logs during export generation
- [x] Phase 13: Export generation completes in reasonable time

---

## Verification Checklist

All of the following must be checked before wrap-up:

- [x] All implementation tasks above are marked `- [x]`
- [x] No TODOs remain in code
- [x] Backend runs without warnings or errors related to map generation
- [x] Manual testing completed with real mission data
- [x] Map outputs at 4K resolution (3840x2880 pixels)
- [x] Route bounds and padding correct
- [x] Route colors match timeline status
- [x] All POI markers present and correct
- [x] Legend positioned and formatted correctly
- [x] Excel export generates without errors
- [x] PDF export includes map and chart
- [x] MISSION-PLANNING-GUIDE.md updated
- [x] PLAN.md marked as Completed
- [x] CONTEXT.md finalized
- [x] All changes committed and pushed to feat/excel-sheet1-timeline-summary branch
