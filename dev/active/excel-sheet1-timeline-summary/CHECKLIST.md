# Checklist for excel-sheet1-timeline-summary

**Branch:** `feat/excel-sheet1-timeline-summary`
**Folder:** `dev/active/excel-sheet1-timeline-summary/`
**Status:** In Progress
**Skill:** executing-plan-checklist

> This checklist is intentionally extremely detailed and assumes the executor
> has no prior knowledge of the repo or codebase. Every step must be followed
> exactly, in order, without combining or skipping.

---

## Initialization

- [x] Ensure you are on the correct branch:
  - [x] Run:
    ```bash
    git branch
    ```
  - [x] Confirm that the current branch line is:
    ```text
    * feat/excel-sheet1-timeline-summary
    ```
  - [x] If you are on a different branch, switch with:
    ```bash
    git checkout feat/excel-sheet1-timeline-summary
    ```

---

## Phase 1: Preparation & Dependencies

### Add matplotlib and cartopy to requirements.txt

- [x] Open the file `backend/starlink-location/requirements.txt`
- [x] Locate the line containing `reportlab>=4.0.0` (around line 22)
- [x] Add two new lines immediately after the reportlab line:
  ```
  matplotlib>=3.8.0
  cartopy>=0.22.0
  ```
- [x] Save the file
- [x] Expected result: requirements.txt now includes matplotlib and cartopy

### Rebuild Docker environment with new dependencies

- [x] Stop all running containers:
  ```bash
  docker compose down
  ```
- [x] Expected result: Output shows containers stopped and removed

- [x] Rebuild Docker images with no cache:
  ```bash
  docker compose build --no-cache
  ```
- [x] Expected result: Build completes successfully, showing matplotlib and cartopy installation steps
- [x] Note: This may take 5-10 minutes due to cartopy compilation

- [x] Start containers:
  ```bash
  docker compose up -d
  ```
- [x] Expected result: All containers start and show healthy status

- [x] Verify backend is healthy:
  ```bash
  curl http://localhost:8000/health
  ```
- [x] Expected result: JSON response with `"status": "ok"`

### Commit dependency changes

- [x] Stage the requirements file:
  ```bash
  git add backend/starlink-location/requirements.txt
  ```
- [x] Commit with message:
  ```bash
  git commit -m "feat: add matplotlib and cartopy for export visualizations"
  ```
- [x] Push to remote:
  ```bash
  git push -u origin feat/excel-sheet1-timeline-summary
  ```

### Review current exporter implementation

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Read the `generate_xlsx_export()` function (lines 415-430)
- [x] Note how it creates DataFrame objects and writes them to Excel using `pd.ExcelWriter`
- [x] Read the `_segment_rows()` function (lines 271-331) to understand timeline data structure
- [x] Read the color constants at the top of the file (lines 37-48)
- [x] Confirm understanding: The current Excel export uses pandas DataFrames written directly to sheets without any image embedding or cell styling

### Verify data structure access

- [x] Open `backend/starlink-location/app/mission/models.py`
- [x] Locate the `Mission` class definition
- [x] Note the fields: `route` (relationship), `pois` (relationship), metadata fields
- [x] Locate the `MissionTimeline` class definition
- [x] Note the `segments` field (list of TimelineSegment)
- [x] Locate the `TimelineSegment` class definition
- [x] Note fields: `start_time`, `end_time`, `status` (TimelineStatus enum), `x_state`, `ka_state`, `ku_state` (TransportState enum)
- [x] Confirm understanding: Mission provides route/POI access, Timeline provides segments with status and transport states

---

## Phase 2: Geographic Map Implementation

### Create _generate_route_map function skeleton

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Add imports at the top of the file (after existing imports):
  ```python
  import io
  import matplotlib
  matplotlib.use('Agg')  # Must be before pyplot import for headless operation
  import matplotlib.pyplot as plt
  import cartopy.crs as ccrs
  import cartopy.feature as cfeature
  from matplotlib.patches import Rectangle
  from matplotlib.lines import Line2D
  ```
- [x] Find a good location for new helper functions (suggest before `_segment_rows` function around line 270)
- [x] Add new function:
  ```python
  def _generate_route_map(timeline: MissionTimeline, mission: Mission | None = None) -> bytes:
      """Generate geographic map PNG showing route with color-coded segments and POI markers.

      Args:
          timeline: Mission timeline with segments
          mission: Mission object containing route and POI data

      Returns:
          PNG image bytes
      """
      # TODO: Implementation
      pass
  ```
- [x] Save the file

### Implement route waypoint extraction

- [x] In the `_generate_route_map` function, replace the `pass` statement with:
  ```python
      if mission is None or mission.route is None:
          # Return empty/placeholder map if no route
          fig, ax = plt.subplots(figsize=(10, 6))
          ax.text(0.5, 0.5, 'No route data available', ha='center', va='center')
          ax.axis('off')
          buf = io.BytesIO()
          plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
          plt.close(fig)
          buf.seek(0)
          return buf.read()

      # Extract waypoints from route
      waypoints = []
      if hasattr(mission.route, 'geometry') and mission.route.geometry:
          # Parse route geometry (assumed to be list of [lon, lat] or similar)
          # Adjust based on actual Route model structure
          geometry = mission.route.geometry
          if isinstance(geometry, list):
              waypoints = [(pt[0], pt[1]) for pt in geometry if len(pt) >= 2]

      if not waypoints:
          # No valid waypoints
          fig, ax = plt.subplots(figsize=(10, 6))
          ax.text(0.5, 0.5, 'No waypoint data available', ha='center', va='center')
          ax.axis('off')
          buf = io.BytesIO()
          plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
          plt.close(fig)
          buf.seek(0)
          return buf.read()
  ```
- [x] Save the file
- [x] Note: The actual route geometry structure may differ; will adjust after testing

### Implement map projection and base features

- [x] Continue adding to `_generate_route_map` function:
  ```python
      # Create figure with geographic projection
      fig = plt.figure(figsize=(12, 8))
      ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

      # Calculate map bounds from waypoints
      lons = [wp[0] for wp in waypoints]
      lats = [wp[1] for wp in waypoints]
      lon_min, lon_max = min(lons), max(lons)
      lat_min, lat_max = min(lats), max(lats)

      # Add margin (10% on each side)
      lon_margin = (lon_max - lon_min) * 0.1
      lat_margin = (lat_max - lat_min) * 0.1
      ax.set_extent([lon_min - lon_margin, lon_max + lon_margin,
                     lat_min - lat_margin, lat_max + lat_margin],
                    crs=ccrs.PlateCarree())

      # Add map features
      ax.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='none')
      ax.add_feature(cfeature.OCEAN, facecolor='lightblue', edgecolor='none')
      ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
      ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--', alpha=0.5)
      ax.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
  ```

### Implement route path with color-coded segments

- [x] Continue adding to `_generate_route_map` function:
  ```python
      # Map segment status to colors
      status_colors = {
          'NOMINAL': '#00FF00',      # Green
          'DEGRADED': '#FFFF00',     # Yellow
          'CRITICAL': '#FF0000',     # Red
      }

      # Calculate segment boundaries along waypoint indices
      # Assumption: segments are evenly distributed across the route duration
      # Adjust logic based on actual timestamp-to-waypoint mapping
      total_duration = (timeline.segments[-1].end_time - timeline.segments[0].start_time).total_seconds()
      segment_waypoint_ranges = []
      cumulative_time = 0
      waypoint_index = 0

      for segment in timeline.segments:
          seg_duration = (segment.end_time - segment.start_time).total_seconds()
          seg_fraction = seg_duration / total_duration
          waypoints_in_segment = max(1, int(seg_fraction * len(waypoints)))
          start_idx = waypoint_index
          end_idx = min(waypoint_index + waypoints_in_segment, len(waypoints) - 1)
          segment_waypoint_ranges.append((start_idx, end_idx, segment.status.name))
          waypoint_index = end_idx

      # Draw route segments with appropriate colors
      for start_idx, end_idx, status in segment_waypoint_ranges:
          if start_idx >= end_idx:
              continue
          segment_lons = [waypoints[i][0] for i in range(start_idx, end_idx + 1)]
          segment_lats = [waypoints[i][1] for i in range(start_idx, end_idx + 1)]
          color = status_colors.get(status, '#808080')  # Default gray
          ax.plot(segment_lons, segment_lats, color=color, linewidth=2,
                  transform=ccrs.PlateCarree(), zorder=2)
  ```

### Implement POI and airport markers

- [x] Continue adding to `_generate_route_map` function:
  ```python
      # Add departure airport marker (first waypoint)
      if waypoints:
          dep_lon, dep_lat = waypoints[0]
          ax.plot(dep_lon, dep_lat, marker='^', color='blue', markersize=12,
                  transform=ccrs.PlateCarree(), zorder=3)
          ax.text(dep_lon, dep_lat, ' Departure', fontsize=9, color='blue',
                  transform=ccrs.PlateCarree(), zorder=4,
                  verticalalignment='bottom', horizontalalignment='left')

      # Add arrival airport marker (last waypoint)
      if waypoints:
          arr_lon, arr_lat = waypoints[-1]
          ax.plot(arr_lon, arr_lat, marker='v', color='purple', markersize=12,
                  transform=ccrs.PlateCarree(), zorder=3)
          ax.text(arr_lon, arr_lat, ' Arrival', fontsize=9, color='purple',
                  transform=ccrs.PlateCarree(), zorder=4,
                  verticalalignment='top', horizontalalignment='left')

      # Add mission-event POI markers
      if mission.pois:
          for poi in mission.pois:
              if poi.poi_type == 'mission-event':
                  ax.plot(poi.longitude, poi.latitude, marker='o', color='orange',
                          markersize=10, transform=ccrs.PlateCarree(), zorder=3)
                  ax.text(poi.longitude, poi.latitude, f' {poi.name}', fontsize=8,
                          color='orange', transform=ccrs.PlateCarree(), zorder=4,
                          verticalalignment='center', horizontalalignment='left')
  ```

### Add legend and finalize map

- [x] Continue adding to `_generate_route_map` function:
  ```python
      # Create legend
      legend_elements = [
          Line2D([0], [0], color='#00FF00', linewidth=2, label='Nominal'),
          Line2D([0], [0], color='#FFFF00', linewidth=2, label='Degraded'),
          Line2D([0], [0], color='#FF0000', linewidth=2, label='Critical'),
          Line2D([0], [0], marker='^', color='blue', linestyle='None',
                 markersize=8, label='Departure'),
          Line2D([0], [0], marker='v', color='purple', linestyle='None',
                 markersize=8, label='Arrival'),
          Line2D([0], [0], marker='o', color='orange', linestyle='None',
                 markersize=8, label='POI'),
      ]
      ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

      ax.set_title('Mission Route Map', fontsize=14, fontweight='bold')

      # Save to PNG bytes
      buf = io.BytesIO()
      plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
      plt.close(fig)
      buf.seek(0)
      return buf.read()
  ```
- [x] Save the file

### Test map generation

- [x] Rebuild and restart Docker:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Expected result: Backend starts successfully with no import errors

- [x] Test by triggering an export (use existing test or API endpoint)
- [x] If errors occur, check logs:
  ```bash
  docker compose logs -f starlink-location
  ```
- [x] Adjust route geometry parsing based on actual data structure
- [x] Expected result: Map function executes without crashing (visual inspection comes later)

### Commit map implementation

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: implement geographic route map generation"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 3: Timeline Bar Chart Implementation

### Create _generate_timeline_chart function

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Add new function after `_generate_route_map`:
  ```python
  def _generate_timeline_chart(timeline: MissionTimeline) -> bytes:
      """Generate horizontal timeline bar chart showing transport states.

      Args:
          timeline: Mission timeline with segments

      Returns:
          PNG image bytes
      """
      if not timeline.segments:
          # Empty chart
          fig, ax = plt.subplots(figsize=(10, 3))
          ax.text(0.5, 0.5, 'No timeline data available', ha='center', va='center')
          ax.axis('off')
          buf = io.BytesIO()
          plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
          plt.close(fig)
          buf.seek(0)
          return buf.read()

      # Get mission start and end times
      start_time = timeline.segments[0].start_time
      end_time = timeline.segments[-1].end_time
      total_duration = (end_time - start_time).total_seconds()

      # State to color mapping
      state_colors = {
          'AVAILABLE': '#00FF00',    # Green
          'DEGRADED': '#FFFF00',     # Yellow
          'OFFLINE': '#FF0000',      # Red
      }

      # Create figure
      fig, ax = plt.subplots(figsize=(14, 4))

      # Y positions for each transport
      transport_y_positions = {
          'X-Band': 2,
          'Ka (HCX)': 1,
          'Ku (StarShield)': 0,
      }

      # Draw segments for each transport
      for segment in timeline.segments:
          seg_start_offset = (segment.start_time - start_time).total_seconds()
          seg_duration = (segment.end_time - segment.start_time).total_seconds()

          # X-Band
          x_color = state_colors.get(segment.x_state.name, '#808080')
          ax.barh(transport_y_positions['X-Band'], seg_duration, left=seg_start_offset,
                  height=0.8, color=x_color, edgecolor='black', linewidth=0.5)

          # Ka
          ka_color = state_colors.get(segment.ka_state.name, '#808080')
          ax.barh(transport_y_positions['Ka (HCX)'], seg_duration, left=seg_start_offset,
                  height=0.8, color=ka_color, edgecolor='black', linewidth=0.5)

          # Ku
          ku_color = state_colors.get(segment.ku_state.name, '#808080')
          ax.barh(transport_y_positions['Ku (StarShield)'], seg_duration, left=seg_start_offset,
                  height=0.8, color=ku_color, edgecolor='black', linewidth=0.5)

      # Set up axes
      ax.set_yticks([0, 1, 2])
      ax.set_yticklabels(['Ku (StarShield)', 'Ka (HCX)', 'X-Band'])
      ax.set_xlim(0, total_duration)

      # Format x-axis with time labels (HH:MM format from start)
      def format_time_label(seconds, pos):
          hours = int(seconds // 3600)
          minutes = int((seconds % 3600) // 60)
          return f'T+{hours:02d}:{minutes:02d}'

      from matplotlib.ticker import FuncFormatter
      ax.xaxis.set_major_formatter(FuncFormatter(format_time_label))
      ax.set_xlabel('Time from Mission Start', fontsize=10)
      ax.set_title('Transport State Timeline', fontsize=12, fontweight='bold')

      # Add vertical grid lines at 1-hour intervals
      hour_interval = 3600  # seconds
      for hour_mark in range(0, int(total_duration) + hour_interval, hour_interval):
          ax.axvline(x=hour_mark, color='gray', linestyle='--', linewidth=0.5, alpha=0.7)

      # Add legend
      from matplotlib.patches import Patch
      legend_elements = [
          Patch(facecolor='#00FF00', edgecolor='black', label='Available'),
          Patch(facecolor='#FFFF00', edgecolor='black', label='Degraded'),
          Patch(facecolor='#FF0000', edgecolor='black', label='Offline'),
      ]
      ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

      ax.grid(axis='x', alpha=0.3)

      # Save to PNG bytes
      buf = io.BytesIO()
      plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
      plt.close(fig)
      buf.seek(0)
      return buf.read()
  ```
- [x] Save the file

### Test timeline chart generation

- [x] Rebuild and restart Docker:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [x] Expected result: Backend starts successfully

- [x] Test chart generation (will verify visually in Phase 7)

### Commit timeline chart implementation

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: implement timeline bar chart generation"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 4: Summary Table Implementation

### Create _summary_table_rows function

- [x] Open `backend/starlink-location/app/mission/exporter.py`
- [x] Add new function after `_generate_timeline_chart`:
  ```python
  def _summary_table_rows(timeline: MissionTimeline, mission: Mission | None = None) -> pd.DataFrame:
      """Generate simplified summary table DataFrame for Sheet 1.

      Returns DataFrame with columns: Start (UTC), Duration, Status, Systems Down
      """
      rows = []

      for segment in timeline.segments:
          # Format start time in UTC
          start_utc = segment.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')

          # Format duration as HH:MM:SS
          duration_seconds = (segment.end_time - segment.start_time).total_seconds()
          duration_str = _format_seconds_hms(int(duration_seconds))

          # Status
          status = segment.status.name

          # Systems Down - list impacted transports
          systems_down = _serialize_transport_list(segment.impacted_transports)

          rows.append({
              'Start (UTC)': start_utc,
              'Duration': duration_str,
              'Status': status,
              'Systems Down': systems_down,
          })

      return pd.DataFrame(rows)
  ```
- [x] Save the file

### Commit summary table implementation

- [x] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [x] Commit:
  ```bash
  git commit -m "feat: implement summary table generation"
  ```
- [x] Push:
  ```bash
  git push
  ```

---

## Phase 5: Excel Export Integration

### Modify generate_xlsx_export to create Summary sheet

- [ ] Open `backend/starlink-location/app/mission/exporter.py`
- [ ] Locate the `generate_xlsx_export` function (around line 415)
- [ ] Replace the entire function with:
  ```python
  def generate_xlsx_export(timeline: MissionTimeline, mission: Mission | None = None) -> bytes:
      """Return XLSX bytes containing summary (with map/chart), timeline, advisory, and stats sheets."""
      workbook = io.BytesIO()

      # Generate all data
      summary_df = _summary_table_rows(timeline, mission)
      timeline_df = _segment_rows(timeline, mission)
      advisories_df = _advisory_rows(timeline, mission)
      stats_df = _statistics_rows(timeline)

      # Generate images
      route_map_png = _generate_route_map(timeline, mission)
      timeline_chart_png = _generate_timeline_chart(timeline)

      # Write to Excel
      with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
          # Write all sheets (summary will be reordered to position 0 after)
          summary_df.to_excel(writer, sheet_name="Summary", index=False)
          timeline_df.to_excel(writer, sheet_name="Timeline", index=False)
          if not advisories_df.empty:
              advisories_df.to_excel(writer, sheet_name="Advisories", index=False)
          if not stats_df.empty:
              stats_df.to_excel(writer, sheet_name="Statistics", index=False)

          # Access workbook to add images and formatting
          wb = writer.book
          summary_ws = wb["Summary"]

          # Embed route map image at top
          from openpyxl.drawing.image import Image as OpenpyxlImage
          map_img = OpenpyxlImage(io.BytesIO(route_map_png))
          map_img.anchor = 'A1'  # Top-left corner
          summary_ws.add_image(map_img)

          # Calculate row offset for chart (map height + margin)
          # Assume map is ~30 rows tall at default row height
          chart_row = 32

          # Embed timeline chart below map
          chart_img = OpenpyxlImage(io.BytesIO(timeline_chart_png))
          chart_img.anchor = f'A{chart_row}'
          summary_ws.add_image(chart_img)

          # Calculate row offset for table (chart height + margin)
          # Assume chart is ~15 rows tall
          table_start_row = chart_row + 17

          # Move table data down to below images
          # Insert rows at top to push table down
          summary_ws.insert_rows(1, table_start_row - 1)

          # Re-add images (they may have shifted)
          summary_ws._images = []
          map_img = OpenpyxlImage(io.BytesIO(route_map_png))
          map_img.anchor = 'A1'
          summary_ws.add_image(map_img)

          chart_img = OpenpyxlImage(io.BytesIO(timeline_chart_png))
          chart_img.anchor = f'A{chart_row}'
          summary_ws.add_image(chart_img)

          # Apply color formatting to table rows based on Status column
          from openpyxl.styles import PatternFill

          # Find Status column index (column C, index 3)
          status_col_idx = 3

          # Color fills
          green_fill = PatternFill(start_color='00FF00', end_color='00FF00', fill_type='solid')
          yellow_fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
          red_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')

          # Apply to data rows (skip header at table_start_row)
          for row_idx in range(table_start_row + 1, table_start_row + 1 + len(summary_df)):
              status_cell = summary_ws.cell(row=row_idx, column=status_col_idx)
              status_value = status_cell.value

              if status_value == 'NOMINAL':
                  fill = green_fill
              elif status_value == 'DEGRADED':
                  fill = yellow_fill
              elif status_value == 'CRITICAL':
                  fill = red_fill
              else:
                  continue

              # Apply fill to entire row
              for col_idx in range(1, 5):  # Columns A-D
                  summary_ws.cell(row=row_idx, column=col_idx).fill = fill

          # Adjust column widths
          summary_ws.column_dimensions['A'].width = 25  # Start (UTC)
          summary_ws.column_dimensions['B'].width = 15  # Duration
          summary_ws.column_dimensions['C'].width = 12  # Status
          summary_ws.column_dimensions['D'].width = 30  # Systems Down

          # Reorder sheets so Summary is first
          wb._sheets.remove(summary_ws)
          wb._sheets.insert(0, summary_ws)

      workbook.seek(0)
      return workbook.read()
  ```
- [ ] Save the file

### Test Excel export

- [ ] Rebuild and restart Docker:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [ ] Expected result: Backend starts successfully

- [ ] Trigger an export via API or test (will do full verification in Phase 7)
- [ ] If errors occur, check logs and adjust image positioning/table shifting logic

### Commit Excel integration

- [ ] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [ ] Commit:
  ```bash
  git commit -m "feat: integrate map, chart, and summary table into Excel Sheet 1"
  ```
- [ ] Push:
  ```bash
  git push
  ```

---

## Phase 6: PDF Export Integration

### Add timeline chart to PDF export

- [ ] Open `backend/starlink-location/app/mission/exporter.py`
- [ ] Locate the `generate_pdf_export` function (around line 433)
- [ ] Near the end of the function, before the final `return`, add:
  ```python
      # Add timeline chart as new page
      story.append(PageBreak())

      # Generate timeline chart
      timeline_chart_png = _generate_timeline_chart(timeline)

      # Embed chart image
      from reportlab.lib.utils import ImageReader
      chart_img = ImageReader(io.BytesIO(timeline_chart_png))
      chart_width = 7 * inch  # Scale to fit page width
      chart_height = 3 * inch

      story.append(Paragraph("Timeline Chart", heading_style))
      story.append(Spacer(1, 0.2 * inch))
      story.append(Image(io.BytesIO(timeline_chart_png), width=chart_width, height=chart_height))
  ```
- [ ] Note: May need to adjust `heading_style` reference or create new style
- [ ] Save the file

### Test PDF export

- [ ] Rebuild and restart Docker:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [ ] Expected result: Backend starts successfully

- [ ] Trigger PDF export (full verification in Phase 7)

### Commit PDF integration

- [ ] Stage changes:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [ ] Commit:
  ```bash
  git commit -m "feat: add timeline chart to PDF export"
  ```
- [ ] Push:
  ```bash
  git push
  ```

---

## Phase 7: Testing & Verification

### Identify test mission data

- [ ] Use existing mission planning API to find or create a test mission with:
  - Route with multiple waypoints
  - At least 3 POIs of type "mission-event"
  - Timeline with varied segment statuses and transport states
- [ ] Note the mission ID for testing

### Generate Excel export

- [ ] Use API endpoint to generate Excel export for test mission:
  ```bash
  curl -o test_export.xlsx http://localhost:8000/api/missions/{MISSION_ID}/export/xlsx
  ```
- [ ] Replace `{MISSION_ID}` with actual ID
- [ ] Expected result: File `test_export.xlsx` downloaded

### Verify Excel Summary sheet

- [ ] Open `test_export.xlsx` in Excel or LibreOffice Calc
- [ ] Verify "Summary" is the first sheet (leftmost tab)
- [ ] Verify map image is visible at top of sheet:
  - [ ] Route path is drawn
  - [ ] Route segments have different colors
  - [ ] Departure marker (blue) is present and labeled
  - [ ] Arrival marker (purple) is present and labeled
  - [ ] POI markers (orange) are present and labeled with POI names
  - [ ] Legend is visible
  - [ ] Map looks professional and clear
- [ ] Verify timeline chart is visible below map:
  - [ ] Three rows labeled X-Band, Ka (HCX), Ku (StarShield)
  - [ ] Colored blocks span the chart
  - [ ] Time axis shows T+HH:MM labels
  - [ ] Vertical grid lines at 1-hour intervals
  - [ ] Legend is visible
- [ ] Verify summary table is below chart:
  - [ ] Four columns: Start (UTC), Duration, Status, Systems Down
  - [ ] Number of rows matches expected segment count
  - [ ] Start times are in UTC format
  - [ ] Durations are in HH:MM:SS format
  - [ ] Status column shows NOMINAL/DEGRADED/CRITICAL
  - [ ] Systems Down lists transports (or empty for NOMINAL)
  - [ ] Row backgrounds are colored: green (NOMINAL), yellow (DEGRADED), red (CRITICAL)
- [ ] Verify other sheets are unchanged:
  - [ ] "Timeline" sheet exists with all original columns
  - [ ] "Statistics" sheet exists
  - [ ] "Advisories" sheet exists if applicable

### Verify Excel data accuracy

- [ ] Compare Summary table rows with Timeline sheet rows
- [ ] Confirm start times match
- [ ] Confirm statuses match
- [ ] Confirm duration calculations are correct
- [ ] Compare timeline chart colors with Timeline sheet transport state columns
- [ ] Verify chart blocks align with segment durations

### Generate PDF export

- [ ] Use API endpoint to generate PDF export:
  ```bash
  curl -o test_export.pdf http://localhost:8000/api/missions/{MISSION_ID}/export/pdf
  ```
- [ ] Expected result: File `test_export.pdf` downloaded

### Verify PDF timeline chart

- [ ] Open `test_export.pdf` in PDF viewer
- [ ] Navigate to the page with timeline chart (should be after statistics)
- [ ] Verify chart is present and matches Excel version:
  - [ ] Three transport rows visible
  - [ ] Colored blocks match expected states
  - [ ] Time axis labeled
  - [ ] Chart fits page properly
  - [ ] Legend visible

### Check backend logs

- [ ] Review Docker logs for any errors or warnings during export generation:
  ```bash
  docker compose logs starlink-location | rg -i error
  docker compose logs starlink-location | rg -i warning
  ```
- [ ] Expected result: No errors or warnings related to export generation

### Test edge cases

- [ ] Test export for mission with no POIs:
  - [ ] Generate export
  - [ ] Verify map still shows route and airports
  - [ ] Verify no errors occur

- [ ] Test export for mission with single segment:
  - [ ] Generate export
  - [ ] Verify timeline chart still renders
  - [ ] Verify table has one row

- [ ] Test export for very short mission (<30 min):
  - [ ] Generate export
  - [ ] Verify chart time axis adjusts appropriately
  - [ ] Verify no rendering issues

- [ ] Test export for very long mission (>8 hours if available):
  - [ ] Generate export
  - [ ] Verify chart grid intervals are readable
  - [ ] Verify file size is reasonable

### Update CONTEXT.md with testing notes

- [ ] Open `dev/active/excel-sheet1-timeline-summary/CONTEXT.md`
- [ ] In the "Testing Strategy" section, add notes about any adjustments made during testing
- [ ] Save the file

### Commit testing adjustments

- [ ] If any code changes were made during testing, stage them:
  ```bash
  git add backend/starlink-location/app/mission/exporter.py
  ```
- [ ] If CONTEXT.md was updated:
  ```bash
  git add dev/active/excel-sheet1-timeline-summary/CONTEXT.md
  ```
- [ ] Commit:
  ```bash
  git commit -m "test: verify Excel and PDF exports with real mission data"
  ```
- [ ] Push:
  ```bash
  git push
  ```

---

## Phase 8: Documentation & Wrap-Up

### Update MISSION-PLANNING-GUIDE.md

- [ ] Open `docs/MISSION-PLANNING-GUIDE.md`
- [ ] Locate the section describing Excel Sheet 1 (around lines 314-318)
- [ ] Replace the current description with accurate details:
  ```markdown
  **Sheet 1: Summary**

  - Geographic map showing mission route with color-coded segments (green=NOMINAL, yellow=DEGRADED, red=CRITICAL)
  - Labeled markers for departure airport (blue), arrival airport (purple), and mission-event POIs (orange)
  - Horizontal timeline bar chart showing X-Band, Ka, and Ku transport states over time
  - Simplified summary table with columns: Start (UTC), Duration, Status, Systems Down
  - Color-coded table rows matching segment status
  ```
- [ ] Locate the section describing PDF Page 3 timeline chart (around lines 351-356)
- [ ] Update to match actual implementation:
  ```markdown
  **Page 3: Timeline Chart**

  - Horizontal bar chart with three rows (X-Band, Ka, Ku)
  - Color-coded blocks showing transport states: green (AVAILABLE), yellow (DEGRADED), red (OFFLINE)
  - Vertical grid lines at 1-hour intervals
  - Time axis showing mission-relative time (T+HH:MM)
  - Legend explaining color coding
  ```
- [ ] Save the file

### Commit documentation updates

- [ ] Stage changes:
  ```bash
  git add docs/MISSION-PLANNING-GUIDE.md
  ```
- [ ] Commit:
  ```bash
  git commit -m "docs: update MISSION-PLANNING-GUIDE to reflect actual export implementation"
  ```
- [ ] Push:
  ```bash
  git push
  ```

### Update PLAN.md status

- [ ] Open `dev/active/excel-sheet1-timeline-summary/PLAN.md`
- [ ] Change the Status field from "Planning" to "Completed"
- [ ] Save the file

### Finalize CONTEXT.md

- [ ] Open `dev/active/excel-sheet1-timeline-summary/CONTEXT.md`
- [ ] Review all sections for accuracy
- [ ] Update "Last Updated" date to today
- [ ] Add any final notes about implementation decisions or discovered constraints
- [ ] Save the file

### Mark all checklist items complete

- [ ] Review this entire checklist
- [ ] Ensure all tasks are marked `- [x]`
- [ ] Save CHECKLIST.md

### Commit final plan document updates

- [ ] Stage plan documents:
  ```bash
  git add dev/active/excel-sheet1-timeline-summary/PLAN.md
  git add dev/active/excel-sheet1-timeline-summary/CONTEXT.md
  git add dev/active/excel-sheet1-timeline-summary/CHECKLIST.md
  ```
- [ ] Commit:
  ```bash
  git commit -m "docs: finalize plan documents for excel-sheet1-timeline-summary"
  ```
- [ ] Push:
  ```bash
  git push
  ```

### Update LESSONS-LEARNED.md

- [ ] Open `dev/LESSONS-LEARNED.md`
- [ ] Add a new dated entry describing key learnings from this work
- [ ] Save the file

### Commit LESSONS-LEARNED update

- [ ] Stage changes:
  ```bash
  git add dev/LESSONS-LEARNED.md
  ```
- [ ] Commit:
  ```bash
  git commit -m "docs: add lessons learned from excel-sheet1-timeline-summary"
  ```
- [ ] Push:
  ```bash
  git push
  ```

### Verify branch is ready for PR

- [ ] Confirm all changes are committed:
  ```bash
  git status
  ```
- [ ] Expected result: "nothing to commit, working tree clean"

- [ ] Confirm branch is pushed to remote:
  ```bash
  git log origin/feat/excel-sheet1-timeline-summary..HEAD
  ```
- [ ] Expected result: No commits (meaning everything is pushed)

### Ready for wrap-up skill

- [ ] This feature is now complete and ready for PR creation
- [ ] Use the `wrapping-up-plan` skill to create the pull request
- [ ] The wrapping-up skill will handle final archival and PR creation

---

## Documentation Maintenance

- [ ] Update PLAN.md if any phase boundaries changed
- [ ] Update CONTEXT.md if new files, dependencies, assumptions, or risks were discovered
- [ ] Update LESSONS-LEARNED.md when something surprising or important happens

---

## Verification Tasks

- [ ] Manual testing with real mission data completed
- [ ] Excel Summary sheet verified (map, chart, table all correct)
- [ ] PDF timeline chart verified
- [ ] Edge cases tested (no POIs, single segment, short/long missions)
- [ ] No errors in backend logs
- [ ] Data accuracy confirmed (cross-checked with Timeline sheet)

---

## Pre-Wrap Checklist

All of the following must be checked before handoff to `wrapping-up-plan`:

- [ ] All implementation tasks above are marked `- [x]`
- [ ] No TODOs remain in code
- [ ] Backend runs without warnings or errors
- [ ] Tests pass (manual testing completed)
- [ ] PLAN.md updated to "Completed" status
- [ ] CONTEXT.md finalized
- [ ] CHECKLIST.md fully completed
- [ ] MISSION-PLANNING-GUIDE.md documentation updated
- [ ] LESSONS-LEARNED.md updated
- [ ] All changes committed and pushed to feat/excel-sheet1-timeline-summary branch
