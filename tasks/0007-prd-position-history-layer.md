# PRD-0007: Position History Layer with Altitude-Based Coloring

## 1. Introduction/Overview

This feature adds a new visual layer to the Grafana Geomap panel that displays
the Starlink terminal's position history over a configurable time window (up to
the full Prometheus retention period of 15 days). The history will be rendered
as a continuous route line with color gradients representing altitude changes,
providing users with visual insight into their movement patterns and elevation
profile over time.

**Problem Statement:** Currently, the map only shows the Starlink terminal's
current position. Users have no way to visualize where they have been, their
route history, or how their altitude has changed over time. This limits the
ability to analyze movement patterns, understand terrain traversed, or review
past journeys.

**Goal:** Provide a visual representation of the terminal's position history
that preserves the existing current-position functionality while adding rich
historical context through altitude-colored route visualization.

## 2. Goals

1. Display a continuous route line showing position history over a configurable
   time window (6h, 12h, 24h, up to 15 days)
2. Use color gradients on the route line to represent altitude changes with a
   fixed color palette and auto-scaling altitude range
3. Allow users to toggle the history layer on/off without affecting the current
   position marker
4. Enable users to adjust the time window for history display
5. Provide interactive hover/click functionality to display detailed information
   at any point on the route
6. Leverage existing Prometheus time-series data for historical position and
   telemetry
7. Sample position data at 10-second intervals for optimal performance across
   all time ranges
8. Ensure the feature works in both simulation and live modes
9. Handle data gaps gracefully by interpolating between points (Note: dashed
   lines are not technically feasible in Grafana Geomap)
10. Support display of multiple discontinuous route segments when the terminal
    has moved non-continuously

## 3. User Stories

1. **As a recreational user**, I want to see where my Starlink terminal has
   traveled over the last 24 hours so that I can review my journey and see the
   route I took.

2. **As a mobile user**, I want to see altitude changes visualized through color
   on my route so that I can understand the elevation profile of my travel
   without checking individual data points.

3. **As a data analyst**, I want to toggle the position history layer on/off so
   that I can focus on real-time data when needed or review historical patterns
   when analyzing usage.

4. **As a user monitoring network performance**, I want to hover over points on
   my route to see telemetry data (speed, latency, throughput) at that specific
   time and location so that I can correlate network performance with location
   and conditions.

5. **As a user reviewing recent travel**, I want to filter the history by time
   window (6h, 12h, 24h, etc.) so that I can focus on specific time periods
   without visual clutter.

6. **As a user who travels discontinuously**, I want to see separate route
   segments when my terminal has been powered off or moved non-continuously so
   that my route visualization accurately reflects actual travel patterns.

## 4. Functional Requirements

### 4.1 Route Visualization

1. The system must render position history as a continuous line/path using
   Grafana's **Route layer** (Beta feature) on the Geomap panel.
2. The route line must use a **fixed color gradient** based on altitude:
   - Use a perceptually uniform color scale (e.g., "Viridis", "Turbo", or
     similar)
   - Color mapping must **auto-scale** based on the min/max altitude values in
     the current dataset
   - Lower altitudes map to the cool end of the spectrum (blue/green)
   - Higher altitudes map to the warm end of the spectrum (yellow/red)
   - The color mapping should be smooth and continuous across the altitude range
3. The route line must not interfere with or obscure the existing current
   position marker layer.
4. The route line should have a **fixed width of 3-4 pixels** to ensure
   visibility without overwhelming the map.
5. The route line must update automatically as new position data arrives from
   Prometheus.
6. When data gaps exist (e.g., terminal offline), the system must **interpolate
   linearly** between the last known position and the next position.
   - **Note:** Dashed line styling is NOT supported in Grafana Geomap Route
     layer as of current versions. Gaps will appear as regular solid lines
     connecting the last and next known positions.

### 4.2 Data Requirements

1. The system must query Prometheus for historical position data at **10-second
   intervals** (using downsampling/averaging) including:
   - Latitude (`starlink_dish_latitude_degrees`)
   - Longitude (`starlink_dish_longitude_degrees`)
   - Altitude (`starlink_dish_altitude_meters`)
   - Timestamp
2. The system must query Prometheus for associated telemetry data at the same
   10-second intervals:
   - Speed (`starlink_dish_speed_knots`)
   - Heading (`starlink_dish_heading_degrees`)
3. The system must query Prometheus for network metrics at each sampled
   position:
   - Latency (`starlink_network_latency_ms`)
   - Download throughput (`starlink_network_throughput_down_mbps`)
   - Upload throughput (`starlink_network_throughput_up_mbps`)
   - Obstructions (`starlink_dish_obstruction_percent`)
4. The system must combine these separate Prometheus time series into a single
   table/dataframe format with the following columns:
   - `time` (timestamp)
   - `latitude` (number)
   - `longitude` (number)
   - `altitude` (number)
   - `speed` (number)
   - `heading` (number)
   - `latency` (number)
   - `throughput_down` (number)
   - `throughput_up` (number)
   - `obstructions` (number)
5. Position samples must be taken at 10-second intervals across the entire
   configurable time range (up to 15 days, the Prometheus retention period).

### 4.3 User Controls

1. The system must provide a **toggle control** to show/hide the position
   history layer.
   - Default state: **visible**
   - Implementation: Use a Grafana dashboard variable with type "Custom" and
     values "show" and "hide"
   - The toggle must be clearly labeled (e.g., "Position History")
2. The system must provide a **time window selector** with at least the
   following options:
   - Last 6 hours
   - Last 12 hours
   - Last 24 hours (default)
   - Last 3 days
   - Last 7 days
   - Last 15 days (maximum, based on Prometheus retention)
3. Implementation: Use a Grafana dashboard variable with type "Interval" or
   "Custom"
4. The time window selector must immediately update the displayed route when
   changed.
5. All controls must be accessible at the top of the Grafana dashboard as
   dashboard variables.

### 4.4 Interactivity

1. When a user hovers over any point on the route line, the system must display
   a **tooltip** containing:
   - Timestamp (formatted as `YYYY-MM-DD HH:mm:ss`)
   - Position (`Lat: XX.XXXX°, Lon: XX.XXXX°`)
   - Altitude (meters, formatted to 1 decimal place)
   - Speed (knots, formatted to 1 decimal place)
   - Heading (degrees, formatted to 0 decimal places)
   - Network latency (ms, formatted to 1 decimal place)
   - Download throughput (Mbps, formatted to 2 decimal places)
   - Upload throughput (Mbps, formatted to 2 decimal places)
   - Obstruction percentage (%, formatted to 1 decimal place)
2. The tooltip must use Grafana's native tooltip styling for consistency with
   the rest of the dashboard.
3. The tooltip must appear near the cursor and not obscure critical parts of the
   route.
4. The tooltip must disappear when the cursor moves away from the route line.

### 4.5 Multiple Routes / Discontinuous Travel

1. The system should handle discontinuous travel (e.g., terminal powered off and
   moved to a new location) by displaying **separate route segments**.
2. **Technical limitation:** Grafana's Route layer currently connects all data
   points in a single layer, creating unwanted lines between discontinuous
   segments.
3. **Workaround approaches:**
   - **Option A (Recommended):** Accept the limitation and display all points as
     a single route. Document this behavior in user documentation.
   - **Option B (Advanced):** Implement logic to detect large gaps in position
     (e.g., >1km jump or >1 hour gap) and create **separate Geomap layers** for
     each continuous segment.
   - For initial implementation, use **Option A** and note Option B as a future
     enhancement.

### 4.6 Performance

1. The system must efficiently query and render up to 15 days of position data
   at 10-second sampling intervals.
2. Data must be downsampled to 10-second intervals using Prometheus query
   functions (e.g., `avg_over_time()`) to ensure smooth rendering and
   performance.
3. The route rendering must not cause noticeable lag or delay in the Grafana
   dashboard (target: <2 seconds to render route on dashboard load).
4. Prometheus queries should use appropriate step parameters to match the
   10-second sampling requirement.

### 4.7 Compatibility

1. The feature must work in both simulation mode and live mode.
2. The feature must work with the existing Grafana Geomap panel configuration.
3. The feature must not break or interfere with any existing dashboard
   functionality (current position marker, POI markers, etc.).
4. The feature must work with Grafana 9.x and 10.x (current stable versions).

## 5. Non-Goals (Out of Scope)

1. **Historical data export:** This feature will not include the ability to
   export position history to files (GPX, KML, CSV).
2. **Playback/animation:** The route will be displayed statically; there will be
   no "playback" or animated replay of the journey.
3. **Route editing:** Users cannot manually edit or modify the displayed route.
4. **Offline storage beyond Prometheus:** Position history will only be
   available from Prometheus; no separate offline cache or database will be
   created for this feature.
5. **Multi-vehicle tracking:** This feature only displays history for a single
   Starlink terminal, not multiple terminals.
6. **Route statistics panel:** While hover tooltips show data, this PRD does not
   include a separate statistics panel summarizing the entire route (total
   distance, average speed, etc.).
7. **Dashed line styling for gaps:** Due to Grafana Geomap Route layer technical
   limitations, dashed lines cannot be used to indicate interpolated gaps in
   data.
8. **User-customizable color palettes:** The altitude color gradient will use a
   fixed color scheme (e.g., Viridis) and cannot be customized by users in the
   initial implementation.

## 6. Design Considerations

### 6.1 Color Palette

- **Fixed color scale:** Use **Grafana's "Turbo"** or **"Viridis"** gradient for
  altitude visualization.
  - Turbo: Provides good perceptual uniformity and vibrant colors
  - Viridis: Excellent for colorblind accessibility
  - **Recommendation:** Use **Turbo** as default due to better visual contrast
- **Auto-scaling:** The altitude range (min/max) will be automatically
  calculated from the current dataset and mapped to the color gradient.
- Ensure sufficient contrast for visibility on both light and dark map
  backgrounds (test with OpenStreetMap and satellite base layers).

### 6.2 UI Controls Placement

- **Position history toggle:** Implement as a Grafana dashboard variable at the
  top of the dashboard
  - Variable name: `show_position_history`
  - Type: Custom
  - Values: `show,hide`
  - Display name: "Position History"
- **Time window selector:** Implement as a Grafana dashboard variable
  - Variable name: `history_time_window`
  - Type: Custom
  - Values: `6h,12h,24h,3d,7d,15d`
  - Display name: "History Window"
  - Default: `24h`

### 6.3 Tooltip Design

- Use Grafana's native Geomap tooltip styling.
- Format example:
  ```
  Time: 2025-10-24 14:30:15
  Position: Lat: 45.5234°, Lon: -122.6762°
  Altitude: 125.3 m
  Speed: 35.2 knots
  Heading: 287°
  Latency: 42.5 ms
  Download: 125.34 Mbps
  Upload: 12.45 Mbps
  Obstructions: 2.3%
  ```

## 7. Technical Considerations

### 7.1 Grafana Geomap Configuration

This feature will be implemented using **Grafana's Geomap panel** with the
**Route layer** (Beta) capability.

**Key Configuration Points:**

1. **Panel Type:** Geomap (existing panel, add new layer)
2. **Layer Type:** Route (Beta)
3. **Data Source:** Prometheus
4. **Layer Color:** Set to field value (altitude field)
5. **Color Scheme:** Standard options > Color scheme > Turbo (or Viridis)

### 7.2 Prometheus Queries

The system requires multiple Prometheus queries to fetch all necessary metrics.
Each query will retrieve data at 10-second intervals over the selected time
window.

**Query Structure:**

For each metric, use a range query with averaging over 10-second intervals:

```promql
# Query A: Latitude
avg_over_time(starlink_dish_latitude_degrees[$__interval])

# Query B: Longitude
avg_over_time(starlink_dish_longitude_degrees[$__interval])

# Query C: Altitude
avg_over_time(starlink_dish_altitude_meters[$__interval])

# Query D: Speed
avg_over_time(starlink_dish_speed_knots[$__interval])

# Query E: Heading
avg_over_time(starlink_dish_heading_degrees[$__interval])

# Query F: Latency
avg_over_time(starlink_network_latency_ms[$__interval])

# Query G: Download Throughput
avg_over_time(starlink_network_throughput_down_mbps[$__interval])

# Query H: Upload Throughput
avg_over_time(starlink_network_throughput_up_mbps[$__interval])

# Query I: Obstructions
avg_over_time(starlink_dish_obstruction_percent[$__interval])
```

**Query Settings:**

- **Range:** Use dashboard variable `$history_time_window` (e.g., `now-24h` to
  `now`)
- **Step:** Set to `10s` to ensure 10-second sampling
- **Format:** Time series (will be transformed to table format)

### 7.3 Grafana Transformations

After querying Prometheus, apply the following transformations to prepare data
for the Route layer:

**Transformation Pipeline:**

1. **Merge** (or **Outer join** by time)
   - Purpose: Combine all 9 separate time series into a single dataset
   - Settings:
     - Join by: `Time`
     - Mode: Outer join (to preserve all timestamps even if some metrics are
       missing)

2. **Organize fields** (Optional but recommended)
   - Purpose: Rename fields to more user-friendly names
   - Mappings:
     - `starlink_dish_latitude_degrees` → `latitude`
     - `starlink_dish_longitude_degrees` → `longitude`
     - `starlink_dish_altitude_meters` → `altitude`
     - `starlink_dish_speed_knots` → `speed`
     - `starlink_dish_heading_degrees` → `heading`
     - `starlink_network_latency_ms` → `latency`
     - `starlink_network_throughput_down_mbps` → `throughput_down`
     - `starlink_network_throughput_up_mbps` → `throughput_up`
     - `starlink_dish_obstruction_percent` → `obstructions`

3. **Convert field type** (if needed)
   - Purpose: Ensure latitude and longitude are recognized as numbers
   - Settings:
     - Field: `latitude` → Type: `number`
     - Field: `longitude` → Type: `number`
     - Field: `altitude` → Type: `number`
     - (Repeat for all numeric fields)

4. **Filter data by values** (Optional)
   - Purpose: Remove rows where latitude or longitude are missing/null
   - Settings:
     - Include rows where `latitude` is not empty AND `longitude` is not empty

**Expected Output Format:**

After transformations, data should be in table format:

| Time                | latitude | longitude  | altitude | speed | heading | latency | throughput_down | throughput_up | obstructions |
| ------------------- | -------- | ---------- | -------- | ----- | ------- | ------- | --------------- | ------------- | ------------ |
| 2025-10-24 14:30:00 | 45.5234  | -122.6762  | 125.3    | 35.2  | 287     | 42.5    | 125.34          | 12.45         | 2.3          |
| 2025-10-24 14:30:10 | 45.5235  | -122.6763  | 126.1    | 35.5  | 288     | 41.2    | 127.12          | 12.67         | 2.1          |
| ...                 | ...      | ...        | ...      | ...   | ...     | ...     | ...             | ...           | ...          |

### 7.4 Route Layer Configuration (Step-by-Step)

**Step 1: Add a New Layer to Geomap**

1. Open the existing Geomap panel in edit mode
2. In the panel settings on the right, scroll to the **"Data layer"** section
3. Click **"+ Add layer"**
4. Name the new layer: `Position History`

**Step 2: Configure Layer Type**

1. In the new layer settings, set **"Layer type"** to **"Route"** (Beta)
2. The layer will now render data points as connected line segments

**Step 3: Configure Layer Location**

1. Under **"Location"** settings:
   - **Latitude field:** Select `latitude`
   - **Longitude field:** Select `longitude`
2. If these fields don't appear, verify that your transformations correctly
   created these columns

**Step 4: Configure Layer Style**

1. Under **"Style"** settings:
   - **Size (line width):** Set to `3` or `4` (fixed value in pixels)
   - **Color:** Change from "Fixed color" to **field-based**
     - Click the color dropdown
     - Select **"By value"**
     - Choose field: `altitude`
   - **Fill opacity:** Set to `1.0` (fully opaque)
   - **Arrow:** Set to `None` (no directional arrows on the route)

**Step 5: Configure Color Gradient**

1. Scroll down to **"Standard options"** in the panel settings (applies to the
   entire panel, not just the layer)
2. Under **"Color scheme"**, select **"Turbo"** (or **"Viridis"** for
   colorblind-friendly)
3. Under **"Color mode"**, ensure it's set to **"Continuous (gradient)"**
4. The color will now automatically scale based on the min/max altitude values
   in the current dataset

**Step 6: Configure Tooltip**

1. In the layer settings, under **"Tooltip"** or **"Label"** (varies by Grafana
   version):
   - Enable tooltips/labels for the route layer
   - The tooltip will automatically show all fields in the dataset when hovering

**Step 7: Layer Visibility (Toggle Control)**

1. Navigate to **Dashboard Settings** (gear icon at top)
2. Go to **Variables** section
3. Click **"Add variable"**
4. Configure:
   - **Name:** `show_position_history`
   - **Type:** Custom
   - **Label:** Position History
   - **Custom options:** `show,hide`
   - **Default:** `show`
5. Save the variable
6. In the Geomap panel JSON (Advanced), add conditional logic to hide/show the
   layer based on `$show_position_history`
   - **Note:** This may require manual JSON editing or using panel repeats. For
     initial implementation, this toggle can be omitted and added as an
     enhancement.

**Alternative for Toggle (Simpler):**

- Use the layer's built-in visibility toggle (eye icon) in the layer list within
  the Geomap panel editor. This allows users to manually toggle visibility
  without a dashboard variable.

**Step 8: Time Window Configuration**

1. Navigate to **Dashboard Settings** > **Variables**
2. Click **"Add variable"**
3. Configure:
   - **Name:** `history_time_window`
   - **Type:** Custom
   - **Label:** History Window
   - **Custom options:**
     ```
     6h : Last 6 hours,
     12h : Last 12 hours,
     24h : Last 24 hours,
     3d : Last 3 days,
     7d : Last 7 days,
     15d : Last 15 days
     ```
   - **Default:** `24h`
4. Save the variable
5. In the Geomap panel queries, set the time range to:
   - **From:** `now-${history_time_window}`
   - **To:** `now`

### 7.5 Performance Optimization

1. **Downsampling:** By using `avg_over_time()` with 10-second intervals, we
   reduce the number of data points:
   - 24 hours at 10s intervals = 8,640 points
   - 15 days at 10s intervals = 129,600 points
2. **Query efficiency:** Use Prometheus's `step` parameter set to `10s` to match
   the desired sampling rate.
3. **Caching:** Grafana automatically caches query results based on time range
   and refresh settings. Set dashboard refresh to manual or 30s+ to avoid
   excessive re-querying.
4. **Progressive loading (future enhancement):** For very long time ranges,
   consider implementing client-side progressive loading or using lower
   resolution for older data.

### 7.6 Handling Data Gaps

**Current Approach (Linear Interpolation):**

- Grafana's Route layer automatically connects consecutive data points with
  straight lines.
- If there's a gap in data (e.g., terminal offline for 2 hours), the route layer
  will draw a straight line from the last known position to the next position.
- **This is the desired behavior per requirements.**

**Limitation:**

- Dashed or dotted line styles are **NOT supported** in Grafana Geomap Route
  layer as of current versions (Grafana 9.x and 10.x).
- Gaps will appear as regular solid lines.

**Future Enhancement:**

- Monitor Grafana GitHub issues/release notes for dashed line support in Route
  layer.
- If/when supported, add a conditional style rule: "If time gap > 1 hour, use
  dashed line"

### 7.7 Dependencies

1. **Prometheus** must be running and retaining at least the configured time
   window of data (up to 15 days per `PROMETHEUS_RETENTION=15d`).
2. **Backend** must expose position and telemetry metrics with consistent
   timestamps.
3. **Grafana version:** Requires Grafana 9.0+ (for Geomap Route layer Beta
   support).
4. **Route layer availability:** The Route layer is in **Beta** as of Grafana
   10.x. Monitor for changes in future versions.

### 7.8 Known Limitations

1. **Route layer is Beta:** The feature may change or have bugs in future
   Grafana versions.
2. **No dashed line support:** Cannot visually distinguish interpolated gaps
   from actual travel segments using line styles.
3. **Single continuous route:** Cannot automatically split discontinuous routes
   into separate visual segments within a single layer. All points will be
   connected.
4. **Color gradient applies to entire dataset:** Auto-scaling is global; cannot
   have different altitude ranges for different time periods in the same view.

## 8. Implementation Steps for Junior Developer

This section provides a step-by-step guide to implement the position history
layer. Follow these steps in order.

### Phase 1: Setup and Preparation

**Task 1.1: Verify Prometheus Data Availability**

1. Open Prometheus UI at `http://localhost:9090`
2. In the query box, run each of these queries to verify data exists:
   ```promql
   starlink_dish_latitude_degrees
   starlink_dish_longitude_degrees
   starlink_dish_altitude_meters
   starlink_dish_speed_knots
   starlink_dish_heading_degrees
   starlink_network_latency_ms
   starlink_network_throughput_down_mbps
   starlink_network_throughput_up_mbps
   starlink_dish_obstruction_percent
   ```
3. Verify that each query returns data points
4. If any metrics are missing, check that the backend is running and exporting
   metrics

**Task 1.2: Verify Grafana Geomap Panel Exists**

1. Open Grafana at `http://localhost:3000`
2. Navigate to the Starlink dashboard
3. Locate the existing Geomap panel that shows the current position
4. Note the panel name/ID (you'll be adding a layer to this panel)

### Phase 2: Create Dashboard Variables

**Task 2.1: Create Time Window Variable**

1. Click the dashboard settings gear icon at the top right
2. Go to **Variables** in the left sidebar
3. Click **"Add variable"**
4. Fill in the following:
   - **Name:** `history_time_window`
   - **Label:** History Window
   - **Type:** Custom
   - **Custom options:**
     ```
     6h : Last 6 hours,
     12h : Last 12 hours,
     24h : Last 24 hours,
     3d : Last 3 days,
     7d : Last 7 days,
     15d : Last 15 days
     ```
   - **Selection options:**
     - Enable "Include All option": No
     - Default value: `24h`
5. Click **"Apply"**
6. Click **"Save dashboard"** (floppy disk icon at top)

**Task 2.2: Create Position History Toggle Variable (Optional)**

_Note: This step is optional for the initial implementation. You can skip it and
rely on the layer's built-in visibility toggle instead._

1. In Dashboard Settings > Variables, click **"Add variable"**
2. Fill in:
   - **Name:** `show_position_history`
   - **Label:** Position History
   - **Type:** Custom
   - **Custom options:** `show : Show, hide : Hide`
   - **Default value:** `show`
3. Click **"Apply"**
4. Click **"Save dashboard"**

### Phase 3: Add Prometheus Queries to Geomap Panel

**Task 3.1: Open Panel Edit Mode**

1. Find the existing Geomap panel on the dashboard
2. Hover over the panel title, click the dropdown arrow, select **"Edit"**

**Task 3.2: Add Query for Latitude**

1. In the **Query** tab at the bottom, you should see existing queries (e.g.,
   for current position)
2. Click **"+ Query"** to add a new query
3. Configure the new query:
   - **Data source:** Prometheus
   - **Query (PromQL):**
     ```promql
     avg_over_time(starlink_dish_latitude_degrees[10s])
     ```
   - **Legend:** `latitude`
   - **Min step:** `10s`
   - **Format:** Time series
4. Note the **Query letter** (e.g., "B", "C", etc.) - you'll need this for
   transformations

**Task 3.3: Add Queries for Other Metrics**

Repeat the above steps to add queries for each metric. Here's the full list:

| Metric        | PromQL Query                                                 | Legend            | Query Letter |
| ------------- | ------------------------------------------------------------ | ----------------- | ------------ |
| Latitude      | `avg_over_time(starlink_dish_latitude_degrees[10s])`        | `latitude`        | (e.g., B)    |
| Longitude     | `avg_over_time(starlink_dish_longitude_degrees[10s])`       | `longitude`       | (e.g., C)    |
| Altitude      | `avg_over_time(starlink_dish_altitude_meters[10s])`         | `altitude`        | (e.g., D)    |
| Speed         | `avg_over_time(starlink_dish_speed_knots[10s])`             | `speed`           | (e.g., E)    |
| Heading       | `avg_over_time(starlink_dish_heading_degrees[10s])`         | `heading`         | (e.g., F)    |
| Latency       | `avg_over_time(starlink_network_latency_ms[10s])`           | `latency`         | (e.g., G)    |
| Download      | `avg_over_time(starlink_network_throughput_down_mbps[10s])` | `throughput_down` | (e.g., H)    |
| Upload        | `avg_over_time(starlink_network_throughput_up_mbps[10s])`   | `throughput_up`   | (e.g., I)    |
| Obstructions  | `avg_over_time(starlink_dish_obstruction_percent[10s])`     | `obstructions`    | (e.g., J)    |

_Tip: You can duplicate an existing query by clicking the duplicate icon, then
edit the PromQL and legend._

**Task 3.4: Set Time Range to Use Dashboard Variable**

1. At the top of the panel editor, look for **"Time range"** or **"Query
   options"**
2. Set **"From"** to: `now-${history_time_window}`
3. Set **"To"** to: `now`
4. This makes the panel respect the time window variable

### Phase 4: Apply Transformations

**Task 4.1: Add Merge Transformation**

1. In the panel editor, click the **"Transform"** tab (next to Query)
2. Click **"+ Add transformation"**
3. Select **"Merge"** (or **"Outer join"** if Merge isn't available)
4. If using Outer join:
   - Set **"Field"** to `Time`
5. This combines all separate time series into a single table

**Task 4.2: Add Organize Fields Transformation (Optional)**

1. Click **"+ Add transformation"** again
2. Select **"Organize fields"**
3. Rename fields to match expected names:
   - `Value #B` (or whatever your latitude query was) → `latitude`
   - `Value #C` → `longitude`
   - `Value #D` → `altitude`
   - `Value #E` → `speed`
   - `Value #F` → `heading`
   - `Value #G` → `latency`
   - `Value #H` → `throughput_down`
   - `Value #I` → `throughput_up`
   - `Value #J` → `obstructions`
4. Hide any fields you don't need (e.g., metric names, labels)

**Task 4.3: Convert Field Types**

1. Click **"+ Add transformation"**
2. Select **"Convert field type"**
3. Set each field to the correct type:
   - `latitude` → `Number`
   - `longitude` → `Number`
   - `altitude` → `Number`
   - `speed` → `Number`
   - `heading` → `Number`
   - `latency` → `Number`
   - `throughput_down` → `Number`
   - `throughput_up` → `Number`
   - `obstructions` → `Number`

**Task 4.4: Filter Out Empty Rows**

1. Click **"+ Add transformation"**
2. Select **"Filter data by values"**
3. Add a condition:
   - **Field:** `latitude`
   - **Match:** `Is not null`
4. Add another condition (click "+ Add condition"):
   - **Field:** `longitude`
   - **Match:** `Is not null`
5. This removes rows where position data is missing

**Task 4.5: Verify Transformation Output**

1. At the bottom of the Transform tab, click **"Table view"** to see the
   transformed data
2. You should see a table with columns: `Time`, `latitude`, `longitude`,
   `altitude`, `speed`, `heading`, `latency`, `throughput_down`,
   `throughput_up`, `obstructions`
3. Verify that data looks correct (numbers in each column, timestamps in Time)

### Phase 5: Add Route Layer to Geomap

**Task 5.1: Add a New Layer**

1. In the panel editor, click the **panel settings icon** (rightmost tab, looks
   like a sliders icon)
2. Scroll down to **"Data layers"** section
3. You should see the existing layer (e.g., "Markers" for current position)
4. Click **"+ Add layer"**
5. Name the new layer: `Position History Route`

**Task 5.2: Configure Layer Type and Location**

1. In the new layer's settings:
   - **Layer type:** Select **"Route"** (Beta)
   - **Location Mode:** Select `Coords` (latitude/longitude)
   - **Latitude field:** Select `latitude` from the dropdown
   - **Longitude field:** Select `longitude` from the dropdown

**Task 5.3: Configure Route Style**

1. Still in the layer settings, find the **"Style"** section:
   - **Size:** Set to `3` (or `4` for thicker lines)
   - **Color:** Click the color box, then:
     - Change from "Single color" to **"By value"**
     - Select field: `altitude`
   - **Fill opacity:** Set to `1.0` (fully opaque)
   - **Arrow:** Set to `None`

**Task 5.4: Configure Color Gradient**

1. Scroll up to the panel-level **"Standard options"** section (not layer
   settings)
2. Find **"Color scheme"**:
   - Click the dropdown
   - Select **"Turbo"** (or **"Viridis"**)
3. Ensure **"Color mode"** is set to **"Continuous (gradient)"** or similar
4. The route should now display with altitude-based colors

**Task 5.5: Configure Tooltip**

1. In the layer settings or under **"Tooltip"** in panel options:
   - Ensure tooltips are **enabled**
   - Grafana will automatically show all fields when hovering over the route

**Task 5.6: Test the Route Layer**

1. Click **"Apply"** at the top right to apply changes
2. The Geomap should now show:
   - Your existing current position marker
   - A new colored route line showing position history
3. Hover over the route to verify the tooltip shows all data fields
4. Try changing the `history_time_window` variable at the top - the route should
   update

### Phase 6: Fine-Tuning and Testing

**Task 6.1: Adjust Layer Order**

1. In the Geomap panel editor, under **"Data layers"**:
   - Drag and drop layers to reorder them
   - Ensure the **current position marker layer** is **above** the route layer
     (so it's not obscured)

**Task 6.2: Test Different Time Windows**

1. Save the dashboard
2. Use the **"History Window"** dropdown at the top to test different time
   ranges:
   - Last 6 hours
   - Last 24 hours
   - Last 15 days
3. Verify that the route updates correctly for each time range

**Task 6.3: Test Toggle (If Implemented)**

1. If you created the `show_position_history` variable:
   - Toggle between "Show" and "Hide"
   - The route layer should appear/disappear accordingly
2. If not implemented, use the **eye icon** next to the layer name in the panel
   editor to toggle visibility

**Task 6.4: Test in Simulation and Live Modes**

1. **Simulation mode:**
   - Ensure `STARLINK_MODE=simulation` in `.env`
   - Restart backend: `docker compose restart backend`
   - Verify that the route appears with simulated movement
2. **Live mode (if hardware available):**
   - Ensure `STARLINK_MODE=live` in `.env`
   - Restart backend: `docker compose restart backend`
   - Verify that the route shows actual terminal movement

**Task 6.5: Verify Performance**

1. Load the dashboard with a 24-hour time window
2. Measure load time (should be <2 seconds)
3. If slow, check:
   - Prometheus query performance in Prometheus UI
   - Number of data points (should be ~8,640 for 24h at 10s intervals)
4. If necessary, increase the sampling interval to 30s or 60s to reduce data
   points

**Task 6.6: Test Edge Cases**

1. **No data scenario:**
   - Stop the backend: `docker compose stop backend`
   - Refresh the dashboard
   - Verify that the panel shows "No data" or gracefully handles the absence of
     data
   - Restart backend: `docker compose start backend`
2. **Data gaps:**
   - If you have historical data with gaps (e.g., terminal offline), verify that
     the route interpolates with straight lines between gaps

**Task 6.7: Document User Instructions**

1. Update the project README or user documentation with:
   - How to use the position history layer
   - How to change the time window
   - How to toggle visibility
   - Note about interpolation during data gaps

### Phase 7: Finalization

**Task 7.1: Save Dashboard Configuration**

1. Click **"Save dashboard"** (floppy disk icon) at the top
2. Add a note: "Added position history route layer with altitude-based coloring"
3. If using Grafana provisioning (config files), export the dashboard JSON and
   save it to the appropriate directory

**Task 7.2: Commit Changes to Git**

1. If dashboard is provisioned via JSON files:
   ```bash
   git add monitoring/grafana/dashboards/starlink-dashboard.json
   git commit -m "feat: add position history layer with altitude-based coloring"
   ```

**Task 7.3: Update Documentation**

1. Add a section to `CLAUDE.md` or project documentation describing the new
   feature:
   - What it does
   - How to use it
   - Known limitations (no dashed lines, single continuous route)

**Task 7.4: Final Testing Checklist**

- [ ] Position history route displays correctly with altitude-based colors
- [ ] Current position marker is still visible and not obscured
- [ ] Tooltip shows all required data fields when hovering over the route
- [ ] Time window selector works and updates the route
- [ ] Toggle control works (if implemented) or layer eye icon toggles visibility
- [ ] Performance is acceptable (<2 seconds load time for 24h window)
- [ ] Works in both simulation and live modes
- [ ] Dashboard saves and persists configuration correctly

## 9. Success Metrics

1. **Feature Adoption:**
   - At least 70% of active users interact with the position history layer
     (toggle it or change time window) within the first week of release.

2. **Performance:**
   - Dashboard load time with position history enabled does not increase by more
     than 15% compared to baseline.
   - Route rendering completes within 2 seconds for 24-hour time windows on
     typical hardware.

3. **Data Accuracy:**
   - Route visualization matches Prometheus data with 100% accuracy (no missing
     segments or incorrect positions, excluding expected data gaps).
   - Altitude-based color gradient correctly reflects the altitude range in the
     dataset.

4. **Usability:**
   - User testing or feedback shows that 80% of users can successfully toggle
     the layer and change the time window without assistance.
   - Users report that the altitude-based coloring is intuitive and helps
     understand elevation changes.

5. **System Stability:**
   - No new errors or crashes related to the position history feature.
   - Prometheus query load remains within acceptable limits (<10% increase in
     query volume).

## 10. Open Questions (Resolved)

The user has provided answers to all open questions:

1. **Color scale configuration:**
   - ✅ **Resolved:** Use a **fixed color palette** (Turbo or Viridis).
   - ✅ **Resolved:** Altitude range will **auto-scale** based on current dataset
     min/max values.

2. **Downsampling strategy:**
   - ✅ **Resolved:** Sample at **10-second intervals** for all time ranges (6h
     to 15 days).

3. **Grafana panel type:**
   - ✅ **Resolved:** Implement in the **existing Geomap panel** using the
     **Route layer** (Beta).
   - ✅ **Resolved:** No limitations identified for altitude-based gradient
     rendering.

4. **Handling data gaps:**
   - ✅ **Resolved:** **Interpolate gaps with straight lines** (solid, not
     dashed due to technical limitations).

5. **Multiple routes:**
   - ✅ **Resolved:** Display **separate route segments** if there are
     discontinuous journeys. Accept limitation that all points connect; consider
     multi-layer approach as future enhancement if needed.

6. **Future enhancements:**
   - Noted: The system can be expanded in the future to support other color
     coding options (speed, latency, signal strength).

---

## 11. Known Technical Limitations (Summary)

1. **Dashed line styling is NOT supported** in Grafana Geomap Route layer (as of
   Grafana 10.x). Data gaps will be interpolated with regular solid lines.
2. **Route layer is in Beta** and may have breaking changes in future Grafana
   versions.
3. **Multiple discontinuous routes** will be connected unless separate layers
   are created (workaround available but not in initial scope).
4. **Color gradient auto-scaling** is global; cannot have different altitude
   ranges for different time periods within the same view.

---

**Document Version:** 1.0
**Created:** 2025-10-24
**Author:** Generated via /create-prd
**Status:** Final - Ready for Implementation
