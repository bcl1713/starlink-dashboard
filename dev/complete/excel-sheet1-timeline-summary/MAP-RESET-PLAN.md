# Map Reset Implementation Plan

**Branch:** `feat/excel-sheet1-timeline-summary`
**Status:** Ready to begin Phase 7 map reset
**Date:** 2025-11-18

---

## Overview

Complete reset of map generation logic to produce proper 4K resolution output (3840x2880 pixels @ 300 DPI). Implementation proceeds in small, testable steps with a STOP after each phase to verify visual output before proceeding.

---

## Implementation Phases (with testing stops)

### Phase 1: Base 4K Canvas (NO CONTENT)
- Output dimensions: 3840x2880 pixels
- Full-frame with no borders, margins, or metadata
- Empty geographic projection canvas
- **STOP & TEST:** Verify canvas aspect ratio and size

### Phase 2: Route Bounds Calculation
- Extract route waypoints from route data
- Calculate extent (min/max lat/lon)
- Apply smart 5% padding:
  - If lon_extent >= lat_extent: pad E/W, height adjusts
  - Else: pad N/S, width adjusts
- Set map bounds to padded area (not drawing route yet)
- **STOP & TEST:** Verify correct area is centered and padded correctly

### Phase 3: Draw Route as Simple Line
- Extract waypoints from `route.points`
- Draw connected line in single color (dark blue)
- No color coding yet, no legend
- **STOP & TEST:** Verify route geometry is correct and follows expected path

### Phase 4: Add Color-Coded Segments
- Color segments by TimelineStatus (green=NOMINAL, yellow=DEGRADED, red=CRITICAL)
- Use time-interpolation to map waypoints to timeline segments
- Implement IDL crossing detection (skip segments crossing ±180°)
- **STOP & TEST:** Verify colors match timeline data and IDL logic works

### Phase 5: Add POI & Airport Markers
- Departure airport marker at route start (distinct style)
- Arrival airport marker at route end (distinct style)
- Mission-event POI markers at correct coordinates
- All markers labeled with readable text
- Positioned to avoid obscuring route
- **STOP & TEST:** Verify all markers present and correctly positioned

### Phase 6: Add Legend Inset
- Legend overlaid on map (e.g., lower-right corner)
- Show route status colors and meanings
- Show marker type meanings
- Must NOT extend beyond figure boundaries
- **STOP & TEST:** Verify legend position and text readable

### Phase 7: Full Integration & Final Testing
- Ensure map integrates correctly into Excel and PDF
- Timeline chart and summary table unchanged
- Test with real mission data
- **STOP & TEST:** Verify complete integration

### Phase 8: Documentation & Wrap-Up
- Update MISSION-PLANNING-GUIDE.md with map specs
- Finalize plan documents
- Create PR

---

## Current Status

**Completed:**
- ✅ Phases 1-6 of original plan (map, chart, summary table, Excel, PDF integration all implemented)
- ✅ Chart and table functionality working
- ✅ Docker environment with matplotlib/cartopy installed

**Issue to Fix:**
- ❌ Map output has broken aspect ratio (1280x1024 too wide/short)
- ❌ Legend takes up 40% of figure space
- ❌ Need complete reset to 4K baseline with smart padding

**Action Items:**
1. Start Phase 1 (base 4K canvas)
2. Build and test after each phase
3. Stop before each phase for user verification

---

## Implementation Location

**File:** `backend/starlink-location/app/mission/exporter.py`
**Function:** `_generate_route_map()` (lines 300-343)

This function will be rewritten from scratch following the phased approach above.

---

## Next Steps

1. Read current `_generate_route_map()` implementation
2. Begin Phase 1: Create base 4K canvas
3. Build Docker image
4. Export test mission and verify output
5. Stop for user verification
6. Proceed to Phase 2 when ready
