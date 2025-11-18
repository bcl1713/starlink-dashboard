# Context for excel-sheet1-timeline-summary

**Branch:** `feat/excel-sheet1-timeline-summary`
**Folder:** `dev/active/excel-sheet1-timeline-summary/`
**Last Updated:** 2025-11-17

---

## Background

The MISSION-PLANNING-GUIDE.md documentation describes a 3-sheet Excel export with Sheet 1 being a "Timeline Summary" containing color-coded rows, simplified columns, and visual highlights for risk windows. However, the actual implementation (`backend/starlink-location/app/mission/exporter.py`) only generates two sheets: "Timeline" (detailed segment breakdown) and "Statistics". This creates a gap between documented and actual behavior.

Additionally, the guide describes a PDF Page 3 "Timeline Chart" showing a horizontal bar visualization of X-Band/Ka/Ku transport states over time, which also does not exist in the current implementation.

This work closes both gaps by:
1. Adding the missing Excel Sheet 1 with enhanced visualizations (geographic map + timeline chart + summary table)
2. Implementing the PDF timeline chart
3. Updating documentation to match reality

This was prompted by user feedback noticing the discrepancy and requesting production-quality visualizations for mission planning workflows.

---

## Relevant Code Locations

**Main implementation files:**
- `backend/starlink-location/app/mission/exporter.py` — Export generation logic (lines 415-589)
  - Lines 415-430: `generate_xlsx_export()` — Excel workbook creation
  - Lines 433-568: `generate_pdf_export()` — PDF document creation
  - Lines 271-331: `_segment_rows()` — Detailed timeline DataFrame
  - Lines 365-378: `_statistics_rows()` — Statistics DataFrame
  - Lines 37-48: Color constants and display names

**Data models:**
- `backend/starlink-location/app/mission/models.py` — Mission, Timeline, Segment models
  - `Mission` class — Contains route, POIs, metadata
  - `MissionTimeline` class — Contains segments list
  - `TimelineSegment` class — start_time, end_time, status, x_state, ka_state, ku_state
  - `TransportState` enum — AVAILABLE, DEGRADED, OFFLINE
  - `TimelineStatus` enum — NOMINAL, DEGRADED, CRITICAL

**Dependencies:**
- `backend/starlink-location/requirements.txt` — Python packages
  - Line 20: `pandas>=2.0.0` — DataFrame manipulation
  - Line 21: `openpyxl>=3.1.0` — Excel file creation
  - Line 22: `reportlab>=4.0.0` — PDF generation

**Documentation:**
- `docs/MISSION-PLANNING-GUIDE.md` — User-facing export documentation
  - Lines 314-318: Sheet 1 description (currently inaccurate)
  - Lines 351-356: PDF Page 3 timeline chart description

**Tests:**
- `backend/starlink-location/tests/unit/test_mission_exporter.py` — Exporter tests
  - Lines 128-136: Test verifies only "Timeline" and "Advisories" sheets exist (will need update)

---

## Dependencies

**New Python libraries to add:**
- `matplotlib>=3.8.0` — Chart and map generation
- `cartopy>=0.22.0` OR `basemap>=1.3.0` — Geographic coordinate projection (cartopy preferred as basemap is deprecated)

**Existing services/APIs:**
- Mission data from mission planning endpoints (`/api/missions/{id}`)
- Route geometry from route database (KML-derived waypoints)
- POI data from POI database (coordinates, names, types)
- Timeline segment data (status and transport states)

**Environment variables:**
- None new required (uses existing mission database connection)

**Docker:**
- Will need full rebuild: `docker compose down && docker compose build --no-cache && docker compose up -d`
- Required because requirements.txt changes

---

## Constraints & Assumptions

**Constraints:**
- Must maintain backward compatibility with existing "Timeline" and "Statistics" sheets
- Export file size should remain reasonable (images compressed appropriately)
- No performance degradation (export generation should complete in similar time)
- Works in Docker environment (matplotlib must run headless without X11)

**Assumptions:**
- Mission objects always have associated routes with waypoint geometry
- POIs with type "mission-event" are the ones to display on maps
- Departure and arrival airports are identifiable from mission metadata or route endpoints
- Timeline segments always have valid start/end times and transport states
- Color scheme: green=good/nominal, yellow=degraded/warning, red=critical/offline (consistent with existing PDF implementation)
- Maps use standard geographic projection (e.g., Mercator or PlateCarree)
- Timeline charts use UTC time axis (all mission data is UTC-based)

---

## Risks

**Risk 1: Geographic projection library complexity**
- Cartopy/basemap can be heavyweight and difficult to install in Docker
- **Mitigation:** Test installation early in Phase 1; fallback to simpler matplotlib scatter plot if necessary

**Risk 2: Image quality vs file size**
- High-resolution maps increase Excel file size significantly
- **Mitigation:** Use reasonable DPI (150-200) and PNG compression; test file sizes during Phase 5

**Risk 3: Color coding ambiguity**
- Segment status (NOMINAL/DEGRADED/CRITICAL) vs transport state (AVAILABLE/DEGRADED/OFFLINE) use similar names but different contexts
- **Mitigation:** Clearly document which applies where (route segments use status, transport bars use state)

**Risk 4: Breaking existing export consumers**
- Unknown if other systems consume these exports programmatically
- **Mitigation:** New sheet is added (not replacing), so existing sheet structure unchanged

**Risk 5: Timeline chart time axis scaling**
- Missions of vastly different durations (30 min vs 10 hours) may not display well with same grid interval
- **Mitigation:** Dynamically adjust grid interval based on mission duration (1-hour default, adjust if needed)

---

## Critical Bug Fixes Applied

**Issue 1: Excel map showing "No route data available"**
- **Root Cause:** Mission model stores `route_id` (string ID), not a `route` object. The original code tried to access `mission.route` directly, which doesn't exist.
- **Fix:** Updated `_generate_route_map()` to use RouteManager to fetch the actual ParsedRoute object from the route_id. Extracts waypoints from `route.points` (which contain latitude, longitude, altitude).
- **Files Changed:** `backend/starlink-location/app/mission/exporter.py` (lines 300-343)
- **Added:** Global `_route_manager` variable and `set_route_manager()` function (lines 62-68)
- **Main.py:** Added initialization call `exporter.set_route_manager(_route_manager)` (line 134)

**Issue 2: PDF export missing route map and timeline chart**
- **Root Cause:** The `generate_pdf_export()` function was never updated to add the map and chart visualizations, even though they were implemented for Excel.
- **Fix:** Added route map image and timeline chart image to PDF export with proper PageBreak between them. Both have error handling to gracefully show "[unavailable]" message if image generation fails.
- **Files Changed:** `backend/starlink-location/app/mission/exporter.py` (lines 926-951)
- **Added:** Import of `PageBreak` from reportlab.platypus (line 34)

**Status:** All fixes applied, Docker rebuilt and verified working. Backend exports all three formats (CSV, XLSX, PDF) successfully.

---

## Testing Strategy

**Definition of "done and verified":**

1. **Excel export verification:**
   - Generate export for a real mission with known characteristics:
     - Route with at least 10 waypoints spanning significant distance
     - At least 3 mission-event POIs
     - Timeline with mix of NOMINAL, DEGRADED, and CRITICAL segments
     - All three transports (X-Band, Ka, Ku) with varied states
   - Open exported .xlsx file in Excel or LibreOffice
   - Verify Summary sheet is first sheet
   - Verify map image displays correctly:
     - Route path visible and follows expected geometry
     - Segment colors match timeline statuses (cross-check with Timeline sheet)
     - Departure airport marker labeled and positioned correctly
     - Arrival airport marker labeled and positioned correctly
     - All mission-event POI markers labeled and positioned correctly
     - Legend, scale, grid present and readable
   - Verify timeline chart displays correctly:
     - Three rows (X-Band, Ka, Ku) visible
     - Colored blocks match transport states in Timeline sheet
     - Time axis covers full mission duration
     - 1-hour grid lines present
     - Legend present
   - Verify summary table:
     - Row count matches segment count
     - Start times in UTC match Timeline sheet start times
     - Durations formatted as HH:MM:SS and match calculated values
     - Status column matches Timeline sheet status
     - Systems Down lists correct transports for each segment
     - Row background colors: green for NOMINAL, yellow for DEGRADED, red for CRITICAL
   - Verify existing sheets unchanged:
     - Timeline sheet still has all 13 columns
     - Statistics sheet still has expected metrics
     - Advisories sheet present if applicable

2. **PDF export verification:**
   - Generate PDF export for same test mission
   - Open .pdf file
   - Verify timeline chart page exists (Page 3 or after statistics)
   - Verify chart matches Excel version (same data, same colors, same structure)
   - Verify chart fits page properly and is readable

3. **Backend validation:**
   - Monitor backend logs during export generation
   - Confirm no errors or warnings
   - Confirm export completes in reasonable time (<10 seconds for typical mission)

4. **Edge cases:**
   - Mission with no POIs (map should still show route and airports)
   - Mission with single segment (chart should still render)
   - Very short mission (<30 min) and very long mission (>8 hours) — verify chart scales appropriately

---

## References

- **Documentation gap identified:** User feedback noting Sheet 1 missing from actual exports
- **MISSION-PLANNING-GUIDE.md:** Lines 314-356 describe expected but unimplemented features
- **Prior exploration findings:** Agent research confirmed Sheet 1 and PDF Page 3 timeline chart do not exist in codebase
- **Related PRs:** None yet (this is first implementation)
