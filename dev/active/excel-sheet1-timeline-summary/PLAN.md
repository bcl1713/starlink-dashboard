# Plan: Excel Sheet 1 Timeline Summary with Maps and Charts

**Branch:** `feat/excel-sheet1-timeline-summary`
**Slug:** `excel-sheet1-timeline-summary`
**Folder:** `dev/active/excel-sheet1-timeline-summary/`
**Date:** 2025-11-17
**Last Updated:** 2025-11-18 (Phase 8 debugging)
**Owner:** brian
**Status:** Phase 7 COMPLETE ✅ | Phase 8 BLOCKED on Bounds/Projection Issue

---

## Executive Summary

The mission planning Excel export currently generates only two sheets (detailed timeline and statistics), but the documentation promises three sheets including a Sheet 1 "Timeline Summary." This work adds the missing Sheet 1 with production-quality visualizations: a geographic map showing the full route with color-coded segments (green/yellow/red) and POI markers, a horizontal timeline bar chart displaying X-Band/Ka/Ku transport states over time, and a simplified color-coded summary table with UTC timestamps. This enhancement also implements the timeline bar chart for PDF exports (documented but not yet built) and updates documentation to match the actual implementation. The work improves mission planning workflows by providing operators with clear visual summaries of route status, risk windows, and transport availability at a glance.

---

## Objectives

The work will be complete when the following **testable outcomes** are achieved:

- Excel exports include a new "Summary" sheet as the first sheet (Sheet 1)
- Summary sheet contains a production-quality geographic map with proper coordinate projection showing route path, color-coded segments (NOMINAL=green, DEGRADED=yellow, CRITICAL=red), and labeled markers for departure airport, mission-event POIs, and arrival airport
- Summary sheet contains a horizontal timeline bar chart with three rows (X-Band, Ka, Ku) showing transport states over time with color-coded blocks and 1-hour grid lines
- Summary sheet contains a simplified summary table with columns: Start (UTC), Duration, Status, Systems Down, with row background colors matching status (green/yellow/red)
- PDF exports include a new Page 3 with the same horizontal timeline bar chart
- Existing "Timeline" (detailed breakdown) and "Statistics" sheets remain unchanged and functional
- Manual testing with real mission data confirms maps and charts render correctly
- MISSION-PLANNING-GUIDE.md updated to accurately describe the actual implementation
- matplotlib added to requirements.txt for image generation

---

## Phases

### **Phase 1 — Preparation & Dependencies**

**Description:**
Set up the environment, add required dependencies (matplotlib with basemap/cartopy for geographic projections), and verify the current export implementation. Identify all data structures needed for map and chart generation.

**Entry Criteria:**

- Scope locked
- Branch created
- Plan documents created

**Exit Criteria:**

- matplotlib and geographic projection library (basemap or cartopy) added to requirements.txt
- Docker environment rebuilt with new dependencies
- Current exporter.py code reviewed and understood
- All required data (route waypoints, POI coordinates, timeline segments with states) confirmed accessible
- Sample mission data identified for testing

---

### **Phase 2 — Geographic Map Implementation**

**Description:**
Create helper function `_generate_route_map()` that produces a production-quality PNG image showing the route on proper geographic coordinates with color-coded segments and labeled markers for airports and POIs.

**Entry Criteria:**

- Dependencies installed
- Understanding of route/POI data structures

**Exit Criteria:**

- `_generate_route_map(timeline, mission)` function implemented in exporter.py
- Map uses proper geographic coordinate projection (not simple X-Y plot)
- Route path rendered as connected line segments, each colored by segment status
- Departure airport marked with labeled blue marker
- Arrival airport marked with labeled purple marker
- Mission-event POIs marked with labeled orange markers
- Map includes legend, scale, and grid lines
- Function returns PNG image bytes
- Manual visual inspection confirms map quality

---

### **Phase 3 — Timeline Bar Chart Implementation**

**Description:**
Create helper function `_generate_timeline_chart()` that produces a horizontal bar chart showing X-Band/Ka/Ku transport states over time, suitable for both Excel and PDF exports.

**Entry Criteria:**

- matplotlib functional
- Timeline segment data structures understood

**Exit Criteria:**

- `_generate_timeline_chart(timeline)` function implemented in exporter.py
- Chart shows three horizontal rows (X-Band, Ka, Ku)
- Each transport row displays colored blocks for segments based on state (green=AVAILABLE, yellow=DEGRADED, red=OFFLINE)
- Vertical grid lines at 1-hour intervals
- X-axis labeled with time markers
- Y-axis labeled with transport names
- Chart includes legend
- Function returns PNG image bytes
- Manual visual inspection confirms chart quality and accuracy

---

### **Phase 4 — Summary Table Implementation**

**Description:**
Create helper function `_summary_table_rows()` that generates the simplified summary DataFrame with only the key columns needed for Sheet 1.

**Entry Criteria:**

- Timeline segment data accessible
- Understanding of existing `_segment_rows()` function

**Exit Criteria:**

- `_summary_table_rows(timeline, mission)` function implemented in exporter.py
- DataFrame contains columns: Start (UTC), Duration, Status, Systems Down
- Start times formatted in UTC timezone only
- Durations formatted as HH:MM:SS
- Systems Down shows comma-separated list of impacted transports
- Function returns pandas DataFrame ready for Excel export

---

### **Phase 5 — Excel Export Integration**

**Description:**
Modify `generate_xlsx_export()` to create Sheet 1 "Summary" with embedded map, chart, and color-coded summary table, positioned as the first sheet.

**Entry Criteria:**

- All three helper functions implemented (map, chart, summary table)
- openpyxl library understood for image embedding and cell styling

**Exit Criteria:**

- `generate_xlsx_export()` updated to generate Summary sheet
- Map image embedded at top of Summary sheet
- Timeline chart image embedded below map
- Summary table written below chart
- Row background colors applied: green (NOMINAL), yellow (DEGRADED), red (CRITICAL)
- Summary sheet positioned as first sheet (index 0)
- Existing Timeline, Advisories, Statistics sheets unchanged
- Column widths and row heights adjusted for readability
- Manual export test confirms proper rendering in Excel/LibreOffice

---

### **Phase 6 — PDF Export Integration**

**Description:**
Add timeline bar chart to PDF export as Page 3, matching the documented behavior in MISSION-PLANNING-GUIDE.md.

**Entry Criteria:**

- `_generate_timeline_chart()` function working
- PDF export function understood

**Exit Criteria:**

- `generate_pdf_export()` updated to include timeline chart
- Chart embedded as Page 3 (or appropriate page after statistics)
- Chart properly scaled and positioned on PDF page
- Manual PDF export test confirms proper rendering

---

### **Phase 7 — Map Reset: Base 4K Canvas**

**Description:**
Create base map at 4K resolution (3840x2880 pixels @ 300 DPI) with no content. Map fills entire figure with no borders, margins, or metadata. User tests output and verifies canvas dimensions and aspect ratio are correct before proceeding.

**Entry Criteria:**

- Current problematic map code identified
- Requirements locked: 4K output (3840x2880), 300 DPI, full-frame

**Exit Criteria:**

- `_generate_route_map()` rewritten to output 4K canvas
- No route, no POIs, no text overlays
- Docker environment rebuilt
- User runs test export, verifies map dimensions and aspect ratio visually
- STOP: Wait for user verification before Phase 8

---

### **Phase 8 — Map: Calculate & Display Route Bounds** ⚠️ BLOCKED

**Description:**
Calculate map bounds from route waypoints with smart 5% padding. Display bounds as initial view (no route drawn yet, just the projected area). User verifies bounds are correct and padding is smart (5% on larger dimension).

**Entry Criteria:**

- Base 4K map rendering correctly ✅
- User confirmed canvas looks good ✅

**Current Status:** 🔴 BLOCKED - Cannot display trans-Pacific IDL-crossing routes

**Blocking Issue:**
Phase 8 attempted to implement route bounds calculation for a trans-Pacific route (Korea to DC) crossing the International Date Line (longitude span: -160° to 170°, 330° total). Five different approaches were tried, all failed:

1. **Pacific-centered projection with coordinate transformation** - NaN/Inf axis limits error
2. **IDL detection with [0,360) normalization** - Bounds collapsed to 3° window around DC
3. **Aspect ratio fix for standard routes** - Blank map regression
4. **[0,360) coordinate space normalization** - Map showed Spain instead of Pacific
5. **Simplified raw bounds with 5% padding** - Map distorted with incorrect aspect ratio

**Root Cause:** PlateCarree projection cannot handle extents spanning >180° longitude with standard `set_extent()` method. The 330° route span exceeds the valid range for standard projection configuration.

**Next Steps Required:**
- Research cartopy documentation for IDL-crossing route best practices
- Consider alternative projections (Orthographic, Mollweide, Robinson)
- OR defer IDL handling to Phase 9 route drawing to unblock progress
- See CONTEXT.md "Phase 8 Investigation Summary" for detailed analysis

**Exit Criteria (unchanged):**

- Calculate route waypoint extents (min/max lat/lon)
- Apply 5% smart padding:
  - If (lon_extent >= lat_extent): pad east/west, height adjusts for aspect ratio
  - Else: pad north/south, width adjusts for aspect ratio
- Map bounds set to these padded coordinates
- User tests export, verifies correct area is shown with proper padding
- STOP: Wait for user verification before Phase 9

---

### **Phase 9 — Map: Draw Route as Simple Line**

**Description:**
Draw route as single-color connected line (no color coding yet). Route follows waypoints from route data. User verifies route geometry is correct and follows expected path.

**Entry Criteria:**

- Route bounds calculating correctly
- Map centering on correct area

**Exit Criteria:**

- Route waypoints extracted from `route.points`
- Connected line drawn through all waypoints in order
- Single color (e.g., dark blue) for entire route
- No legend or additional elements
- User tests export, verifies route path matches expected geography
- STOP: Wait for user verification before Phase 10

---

### **Phase 10 — Map: Add Color-Coded Segments**

**Description:**
Color each route segment according to TimelineStatus (green=NOMINAL, yellow=DEGRADED, red=CRITICAL). Use time-interpolation to map waypoints to timeline segments. User verifies colors match timeline data and IDL crossing logic works (segments crossing ±180° skipped).

**Entry Criteria:**

- Route line rendering correctly
- Time-interpolation algorithm available

**Exit Criteria:**

- Map segments colored by TimelineStatus
- Time-interpolation maps waypoints to timeline segments
- IDL crossing detection: segments crossing ±180° longitude skipped
- Route displays multi-colored according to status timeline
- User tests export, verifies colors match Timeline sheet
- STOP: Wait for user verification before Phase 11

---

### **Phase 11 — Map: Add POI & Airport Markers**

**Description:**
Add labeled markers: departure airport (start), arrival airport (end), and mission-event POIs (at correct coordinates). Markers positioned to not obscure route. User verifies all markers present and correctly positioned.

**Entry Criteria:**

- Color-coded route rendering correctly
- Route geometry stable

**Exit Criteria:**

- Departure airport marker at route start (distinct style/color)
- Arrival airport marker at route end (distinct style/color)
- Mission-event POI markers at correct coordinates (distinct style/color)
- All markers labeled with readable text
- Markers positioned to avoid overlapping route line
- User tests export, verifies all markers present and correctly positioned
- STOP: Wait for user verification before Phase 12

---

### **Phase 12 — Map: Add Legend Inset**

**Description:**
Add legend overlaid inset on map (e.g., lower-right corner). Legend shows color meanings (NOMINAL green, DEGRADED yellow, CRITICAL red) and marker meanings (departure, arrival, POIs). Legend must NOT extend beyond figure boundaries.

**Entry Criteria:**

- Route, segments, and POI markers all rendering
- Map at final resolution

**Exit Criteria:**

- Legend inset positioned on map (not extending boundaries)
- Legend shows route status colors and meanings
- Legend shows marker type meanings
- Legend font/size readable and non-overlapping
- User tests export, verifies legend looks correct and doesn't extend figure
- STOP: Wait for user verification before Phase 13

---

### **Phase 13 — Full Integration & Testing**

**Description:**
Ensure map integrates correctly into Excel and PDF exports with timeline chart and summary table unchanged. Manually test with real mission data.

**Entry Criteria:**

- All map elements rendering correctly
- Each component verified independently

**Exit Criteria:**

- Excel export generates without errors
- Sheet 1 displays map at 4K resolution
- Timeline chart unchanged
- Summary table unchanged
- PDF export includes map and chart
- All three sheets/pages render correctly
- User manually tests with real mission data
- STOP: Wait for user verification before Phase 14

---

### **Phase 14 — Documentation & Wrap-Up**

**Description:**
Update MISSION-PLANNING-GUIDE.md with map specifications, finalize plan documents, and prepare for PR creation.

**Entry Criteria:**

- All components tested and verified
- Implementation stable

**Exit Criteria:**

- MISSION-PLANNING-GUIDE.md updated with map specs (4K, 300 DPI, resolution)
- PLAN.md status updated to "Completed"
- CONTEXT.md finalized
- CHECKLIST.md fully checked
- All changes committed to feat/excel-sheet1-timeline-summary branch
- Branch pushed to remote
- Ready for PR creation
