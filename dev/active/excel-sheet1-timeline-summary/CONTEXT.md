# Context for excel-sheet1-timeline-summary

**Branch:** `feat/excel-sheet1-timeline-summary`
**Folder:** `dev/active/excel-sheet1-timeline-summary/`
**Last Updated:** 2025-11-19 (Phase 15 - PR Review Feedback)

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
- **Status:** ❌ REALIZED - Cartopy PlateCarree projection cannot handle trans-Pacific routes crossing IDL

**Risk 2: Image quality vs file size**
- High-resolution maps increase Excel file size significantly
- **Mitigation:** Use reasonable DPI (150-200) and PNG compression; test file sizes during Phase 5
- **Status:** ✅ MITIGATED - 4K resolution (300 DPI) tested successfully in Phase 7

**Risk 3: Color coding ambiguity**
- Segment status (NOMINAL/DEGRADED/CRITICAL) vs transport state (AVAILABLE/DEGRADED/OFFLINE) use similar names but different contexts
- **Mitigation:** Clearly document which applies where (route segments use status, transport bars use state)
- **Status:** ⚠️ NOT YET TESTED - Phase 10 will implement color coding

**Risk 4: Breaking existing export consumers**
- Unknown if other systems consume these exports programmatically
- **Mitigation:** New sheet is added (not replacing), so existing sheet structure unchanged
- **Status:** ✅ MITIGATED - Sheet structure remains backward compatible

**Risk 5: Timeline chart time axis scaling**
- Missions of vastly different durations (30 min vs 10 hours) may not display well with same grid interval
- **Mitigation:** Dynamically adjust grid interval based on mission duration (1-hour default, adjust if needed)
- **Status:** ⚠️ NOT YET TESTED - Phase 3 timeline chart implementation pending

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

## Phase 8 Investigation Summary

Phase 8 (route bounds calculation) attempted to display a trans-Pacific route crossing the International Date Line. Multiple approaches were tried, all failed.

### Route Characteristics
- **Origin:** Korea (~126° longitude)
- **Destination:** Washington DC (~-77° longitude)
- **Route span:** -160° to 170° longitude (330° total span)
- **IDL crossing:** Yes (multiple waypoints cross ±180° boundary)
- **Latitude range:** ~35° to ~38° (relatively narrow N-S span)

### Attempted Solutions

#### Attempt 1: Pacific-Centered Projection with Coordinate Transformation
- **Date:** 2025-11-18
- **Code approach:** Normalize longitudes to [0,360), calculate center longitude, create PlateCarree(central_longitude=center), transform extent coordinates to projection space
- **Error:** `Axis limits cannot be NaN or Inf`
- **Diagnosis:** Coordinate transformation from geographic to projection coordinates produced NaN/Inf values
- **Files modified:** `exporter.py` lines ~450-490

#### Attempt 2: IDL Detection with [0,360) Normalization
- **Date:** 2025-11-18
- **Code approach:** Detect IDL crossing, normalize all coordinates to [0,360), calculate bounds, transform back to [-180,180)
- **Error:** No error, but bounds collapsed to 3° window
- **Diagnosis:** Bounds calculation showed only arrival area (DC vicinity) instead of full Pacific route; normalization logic incorrectly computed extent
- **Symptom:** Map displayed only a narrow slice around Washington DC

#### Attempt 3: Aspect Ratio Fix (Regression)
- **Date:** 2025-11-18
- **Code approach:** Removed IDL-specific logic, implemented standard aspect ratio preservation
- **Error:** Blank map
- **Diagnosis:** Breaking change introduced; map rendering completely stopped working
- **Symptom:** PDF export showed "[Route map unavailable]" message

#### Attempt 4: [0,360) Coordinate Space with Central Longitude
- **Date:** 2025-11-18
- **Code approach:** Normalize route to [0,360), set central_longitude to midpoint of normalized bounds
- **Error:** Map showed wrong geographic area
- **Diagnosis:** Projection centering was incorrect; displayed Spain/Europe instead of Pacific Ocean
- **Symptom:** Map geography didn't match route coordinates at all

#### Attempt 5: Simplified Raw Bounds
- **Date:** 2025-11-18
- **Code approach:** Removed all normalization and IDL-specific code, used raw min/max lat/lon with 5% padding
- **Error:** No error, but map distorted
- **Diagnosis:** Without proper projection handling, map aspect ratio was incorrect and geography stretched
- **Symptom:** Map displayed but with significant visual distortion

### Key Technical Insights

**What Works:**
1. ✅ IDL-crossing detection logic is correct (identifies segments crossing ±180°)
2. ✅ Route data structure is valid (`route.points` with latitude, longitude, altitude)
3. ✅ Phase 7 base 4K canvas renders correctly (3840x2880 @ 300 DPI)
4. ✅ Longitude range correctly identified: -160° to 170° (330° span)

**What Doesn't Work:**
1. ❌ PlateCarree projection with `central_longitude` parameter for IDL-crossing routes
2. ❌ Coordinate transformation between geographic and projection spaces (produces NaN/Inf)
3. ❌ [0,360) normalization approaches (bounds collapse or show wrong area)
4. ❌ Simple min/max bounds without projection awareness (causes distortion)

**Root Cause Analysis:**
The core issue is that PlateCarree projection expects extents within a single 360° longitude cycle. When a route spans from -160° to +170°, the extent is 330° wide, which exceeds the valid range for standard PlateCarree extent setting. Cartopy's `set_extent()` method cannot handle this case with the standard projection configuration.

### Recommended Next Approach

Based on the investigation, the next attempt should focus on **projection selection** rather than coordinate transformation:

1. **Research cartopy documentation** for IDL-crossing route best practices
2. **Consider alternative projections:**
   - Orthographic (centered on Pacific) - shows globe-like view
   - Mollweide - better for wide longitude spans
   - Robinson - good for global routes
3. **Consider deferring IDL handling to Phase 9:**
   - Simplify Phase 8 to use standard bounds (may look incorrect)
   - Implement proper IDL handling in Phase 9 when drawing route segments
   - This unblocks progress while addressing the visualization issue separately

### Data Structures Available

For the next implementation attempt, these data structures are confirmed working:

```python
# Route object (from RouteManager)
route = route_manager.get_route(mission.route_id)
route.points  # List[RoutePoint] with latitude, longitude, altitude

# Example route point
point.latitude   # float (-90 to 90)
point.longitude  # float (-180 to 180)
point.altitude   # float (meters)

# Bounds calculation (current Phase 8 code)
lons = [p.longitude for p in route.points]
lats = [p.latitude for p in route.points]
min_lon, max_lon = min(lons), max(lons)  # -160.0, 170.0
min_lat, max_lat = min(lats), max(lats)  # ~35.0, ~38.0

# IDL crossing detection (working)
idl_crossing_segments = []
for i in range(len(route.points) - 1):
    if abs(route.points[i+1].longitude - route.points[i].longitude) > 180:
        idl_crossing_segments.append(i)
# Result: [several segment indices where route crosses IDL]
```

---

## Critical Blockers

**BLOCKER 1: Phase 8 Map Bounds Calculation for IDL-Crossing Routes**
- **Status:** BLOCKING all subsequent phases (9-14)
- **Severity:** High - feature cannot progress without resolution
- **Attempted solutions:** 5 different approaches, all failed
- **Impact:** Cannot display trans-Pacific routes correctly
- **Next steps:** Need fresh perspective on cartopy projection selection/configuration
- **Alternative:** Consider deferring IDL handling to Phase 9 route drawing to unblock Phase 8

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

## PR Review Feedback (Phase 15)

**PR #10 Status:** OPEN (2025-11-19)

**Reviewer:** gemini-code-assist (bot)

**10 Code Review Comments:**
1. Color code inconsistency (HIGH) - legend colors don't match route colors
2. Silent Excel error handling (HIGH) - bare `pass` on image embedding
3. Silent PDF error handling (HIGH) - no logging on PDF image generation
4. Redundant base map code (MEDIUM) - generated 3 times for different early-returns
5. Redundant IDL crossing logic (MEDIUM) - duplicated append blocks in geojson.py
6. Logger inside function (MEDIUM) - should be at module level
7. Commented exploration code (MEDIUM) - clutters readability
8. Redundant coordinates init (MEDIUM) - duplicate initialization in geojson.py
9. Docker layer optimization (MEDIUM) - multiple RUN commands can be combined
10. All issues identified are quality/maintainability focused, not blocking functionality

**Phase 15 Plan:** Address all 10 comments systematically (see PLAN.md Phase 15 for details)

---

## References

- **Documentation gap identified:** User feedback noting Sheet 1 missing from actual exports
- **MISSION-PLANNING-GUIDE.md:** Lines 314-356 describe expected but unimplemented features
- **Prior exploration findings:** Agent research confirmed Sheet 1 and PDF Page 3 timeline chart do not exist in codebase
- **PR #10:** https://github.com/bcl1713/starlink-dashboard/pull/10 - Code review feedback with 10 items
- **Related PRs:** Previous implementation PRs (details in git history)
