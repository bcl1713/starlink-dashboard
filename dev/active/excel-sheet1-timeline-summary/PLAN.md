# Plan: Excel Sheet 1 Timeline Summary with Maps and Charts

**Branch:** `feat/excel-sheet1-timeline-summary`
**Slug:** `excel-sheet1-timeline-summary`
**Folder:** `dev/active/excel-sheet1-timeline-summary/`
**Date:** 2025-11-17
**Owner:** brian
**Status:** Phase 7 (Testing & Verification - In Progress)

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

### **Phase 7 — Testing & Verification**

**Description:**
Manually test exports with real mission data to verify all visualizations render correctly and accurately reflect the underlying data.

**Entry Criteria:**

- All implementation complete
- Sample mission data available

**Exit Criteria:**

- Excel export manually tested with real mission containing route, POIs, and varied timeline segments
- Map confirms: route path correct, segment colors match statuses, POI/airport markers correctly positioned and labeled
- Timeline chart confirms: transport states match segment data, time axis accurate, colors correct
- Summary table confirms: times in UTC, durations calculated correctly, row colors match statuses
- PDF export manually tested and timeline chart verified
- No errors or warnings in backend logs during export generation
- Export generation completes in reasonable time (no performance issues)

---

### **Phase 8 — Documentation & Wrap-Up**

**Description:**
Update MISSION-PLANNING-GUIDE.md to accurately describe the actual implementation, finalize plan documents, and prepare for PR creation.

**Entry Criteria:**

- All testing passed
- Implementation verified working

**Exit Criteria:**

- MISSION-PLANNING-GUIDE.md updated with accurate descriptions of Sheet 1 content and PDF Page 3
- Any discrepancies between documentation and implementation resolved
- PLAN.md status updated to "Completed"
- CONTEXT.md finalized
- CHECKLIST.md fully checked
- All changes committed to feat/excel-sheet1-timeline-summary branch
- Branch pushed to remote
- Ready for PR creation via wrapping-up skill
