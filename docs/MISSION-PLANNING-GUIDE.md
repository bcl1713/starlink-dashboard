# Mission Communication Planning Guide

**Last Updated:** 2025-11-16 **Phase:** 5.3 (Comprehensive Documentation)
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Step-by-Step Workflow](#step-by-step-workflow)
4. [Communication Systems Explained](#communication-systems-explained)
5. [Understanding Timeline Segments](#understanding-timeline-segments)
6. [Export Formats](#export-formats)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The Starlink mission communication planner helps flight crews and mission
planners predict how well aircraft can communicate during flight. It accounts
for satellite coverage, antenna pointing constraints, and air-refueling windows
to show exactly when communication will be **nominal** (all systems working),
**degraded** (one system down), or **critical** (two+ systems down).

**Three Independent Communication Systems:**

- **X-Band:** Military satellite system with fixed azimuth dead zones and manual
  handoff points
- **Ka (CommKa):** Commercial satellite constellation with automated coverage
  transitions
- **Ku (StarShield):** LEO constellation backup system, always available unless
  manually flagged out

The planner runs in your web browser and outputs three briefing formats: CSV
(data), Excel (teams), and PDF (stakeholders).

---

## Getting Started

### Access the Planner

1. Open your browser and navigate to:
   `http://<dashboard-url>/ui/mission-planner`
2. The interface loads a four-step form
3. You do **not** need Grafana or Prometheus experience—the planner is
   self-contained

### Requirements

- Valid KML route file (provided by flight planning)
- Route must have at least 2 waypoints
- Basic information: mission name, planned duration

### What You'll Need to Know

- **Route file:** KML format with LineString geometry (standard flight planning
  output)
- **Transports:** Which satellites your aircraft can reach (pre-configured for
  your platform)
- **AAR windows:** If refueling, specify start/end waypoints on your route
- **X transitions:** Manual coordination points where X-Band satellite handoff
  occurs

---

## Step-by-Step Workflow

### Step 1: Upload Your Route

1. Click **Upload Route**
2. Select your KML file (cross-country, international, etc.)
3. System validates:
   - File has valid XML structure
   - Contains at least one LineString (continuous path)
   - Coordinates are valid lat/lon pairs
4. Click **Confirm** - your route appears on a mini-map

**Example route files:**

- `cross-country.kml` - 100+ waypoints, ~3,944 km
- `simple-circular.kml` - Short test route, ~50 km

---

### Step 2: Configure Communication Systems

The system auto-configures three transports. You specify:

#### X-Band Configuration

- **Initial Satellite:** X-1 or X-2 (which satellite starts active)
- **Transitions:** Manual handoff points
  - Click **Add Transition**
  - Enter **Latitude/Longitude** (exact handoff location)
  - Select **Target Satellite** (X-1 or X-2)
  - System automatically adds ±15 minute degradation buffers

#### Ka Configuration

- **Initial Coverage:** Automatically shows AOR/POR/IOR regions
- **Outages:** Optional - add time windows when Ka is unavailable
- **Coverage Gaps:** System detects automatically (no action needed)

#### Ku Configuration

- **Status:** Always nominal unless flagged
- **Outages:** Optional manual blocks only

---

### Step 3: Define AAR Windows (if applicable)

Air-to-Air Refueling blocks X-Band if the satellite is within plus or minus 45
degrees of the AAR heading.

1. Click **Add AAR Window**
2. Select **Start Waypoint** and **End Waypoint** on your route
3. System marks waypoint range as X-Band DEGRADED as applicable
4. Ka and Ku remain nominal throughout

---

### Step 4: Review Timeline & Export

The system computes a **timeline** showing communication status across your
entire route:

- **Green (Nominal):** All 3 systems active
- **Yellow (Degraded):** 1 system down (X-Band transition, Ka gap, AAR window)
- **Red (Critical):** 2+ systems down simultaneously (rare, but alerts you to
  risk)

#### Export Options

**CSV Format** (Data Integration)

- Flat structure: one row per timeline segment
- Columns: Start Time, End Time, Status, Duration, X-Band State, Ka State, Ku
  State
- Use for: Software integrations, spreadsheet analysis
- Example:
  `2025-03-15T12:00:00Z,2025-03-15T12:15:00Z,DEGRADED,900,DEGRADED,NOMINAL,NOMINAL`

**Excel Format** (Team Briefing)

- Multi-sheet workbook with color coding
- Sheet 1: Timeline summary (color-coded green/yellow/red)
- Sheet 2: Detailed segment breakdown
- Sheet 3: Statistics (total nominal time, risk windows, system status)
- Use for: Mission planning meetings, crew briefings

**PDF Format** (Stakeholder Brief)

- Professional layout with:
  - Route map with color-coded segments
  - Timeline chart (x-axis = time, y-axis = systems)
  - Summary statistics and risk assessment
  - System behavior table
- Use for: Customer delivery, regulatory filing, senior review

---

## Communication Systems Explained

### X-Band (Military Satellite)

**What it is:** Secure military satellite communication; high bandwidth, low
latency.

**Coverage:** Point-to-point (not global). Coverage exists over specific
geographic regions.

**Constraint:** Your aircraft has an **azimuth dead zone**—a direction where the
antenna cannot point at the satellite (typically 90° to 270° from North,
adjustable per mission).

**How it works:**

1. **Nominal:** Satellite is in your antenna's azimuth window AND you have
   line-of-sight
2. **Degraded:** Satellite outside azimuth window (e.g., directly overhead) OR
   aircraft performing aerobatic maneuver
3. **Transition:** Switching from X-1 to X-2 satellite (requires 15 min buffer
   pre/post)
4. **AAR Window:** X-Band goes dark during air refueling (antenna points at
   tanker)

**Typical behavior:**

- Continuous availability over continental US
- 15-minute transitions when crossing satellite seams
- Predictable dead zones (same azimuth every orbit)

---

### Ka (CommKa - High Capacity Satellite)

**What it is:** Commercial very-high-bandwidth satellite system; lower latency
than Ku.

**Coverage:** Footprint includes three overlapping satellite regions:

- **AOR** (Atlantic Ocean Region)
- **POR** (Pacific Ocean Region)
- **IOR** (Indian Ocean Region)

**How it works:**

1. **Nominal:** Aircraft is within coverage footprint (fully automatic)
2. **Degraded:** Aircraft crosses from one satellite footprint to another
   (automatic handoff, <1 sec outage)
3. **Coverage Gap:** International Date Line or polar regions (no service)

**Typical behavior:**

- Automatic, no manual intervention
- Coverage transitions are fast and predictable
- International routes may have 20-30 minute gaps

---

### Ku (StarShield - Backup LEO Constellation)

**What it is:** Lower-bandwidth backup constellation; always available globally.

**Coverage:** Global; multiple satellites in view at all times.

**How it works:**

1. **Always nominal** (default state)
2. **Degraded only if:** You manually flag an outage (rare; e.g., known jamming
   zone)

**Typical behavior:**

- No degradation expected
- Acts as fallback if X-Band and Ka both degrade
- Critical system for ensuring crew connectivity

---

## Understanding Timeline Segments

A **timeline segment** is a period of time where communication status is stable.
Segments change when:

- X-Band transition begins or ends
- Ka satellite handoff occurs
- AAR window starts or ends
- Ku outage flag triggers

### Segment Status Logic

Your aircraft communicates via whichever system is available (priority: X-Band >
Ka > Ku). Status reflects how many systems are degraded:

| Systems Down | Label    | Color  | Risk   |
| ------------ | -------- | ------ | ------ |
| 0            | NOMINAL  | Green  | Low    |
| 1            | DEGRADED | Yellow | Medium |
| 2+           | CRITICAL | Red    | High   |

### Reading the Timeline

Example timeline output:

```
Time              Duration  X-Band          Ka              Ku              Status
09:00:00 - 09:15 15 min    NOMINAL         NOMINAL         NOMINAL         NOMINAL
09:15:00 - 09:30 15 min    DEGRADED (Txn)  NOMINAL         NOMINAL         DEGRADED
09:30:00 - 10:15 45 min    NOMINAL         NOMINAL         NOMINAL         NOMINAL
10:15:00 - 10:20 5 min     NOMINAL         DEGRADED (gap)  NOMINAL         DEGRADED
10:20:00 - 11:00 40 min    NOMINAL         NOMINAL         NOMINAL         NOMINAL
```

**Interpretation:**

- 09:15-09:30: X-Band transitioning to new satellite (crew uses Ka as primary)
- 10:15-10:20: Ka crossing coverage boundary (crew uses X-Band as primary)
- All other times: Multiple systems available (redundancy)

---

## Export Formats

### CSV Export

**File:** `mission-<name>-<timestamp>.csv`

**Format:**

```csv
segment_start_utc,segment_end_utc,segment_duration_seconds,status,x_band_state,ka_state,ku_state,segment_index
2025-03-15T12:00:00Z,2025-03-15T12:15:00Z,900,NOMINAL,NOMINAL,NOMINAL,NOMINAL,1
2025-03-15T12:15:00Z,2025-03-15T12:30:00Z,900,DEGRADED,DEGRADED,NOMINAL,NOMINAL,2
```

**Use cases:**

- Import into flight operations database
- Programmatic alerting (flag if CRITICAL segment > 10 min)
- Statistical analysis (total degradation time, system reliability)

---

### Excel Export

**File:** `mission-<name>-<timestamp>.xlsx`

**Sheet 1: Summary**

- Geographic map showing mission route with color-coded segments (green=NOMINAL, yellow=DEGRADED, red=CRITICAL)
- Map resolution: 3840×2880 pixels @ 300 DPI (12.8" × 9.6" for printing)
- Labeled markers for departure airport (blue), arrival airport (purple), and mission-event POIs (orange)
- Route centered with 5% smart padding (5% on larger dimension, other dimension auto-adjusted for aspect ratio)
- Horizontal timeline bar chart showing X-Band, Ka, and Ku transport states over time
- Simplified summary table with columns: Start (UTC), Duration, Status, Systems Down
- Color-coded table rows matching segment status

**Sheet 2: Detailed Breakdown**

- All three time zones (UTC, Eastern, T+)
- System-by-system status per segment
- Notes column for manual annotations

**Sheet 3: Statistics**

- Total mission duration
- Nominal time / Degraded time / Critical time (hours and percentage)
- System availability chart (X-Band %, Ka %, Ku %)
- Risk assessment summary

---

### PDF Export

**File:** `mission-<name>-<timestamp>.pdf`

**Page 1: Executive Summary**

- Mission name, date, route overview
- Key statistics (total time, degradation windows)
- Risk rating (Green/Yellow/Red)

**Page 2: Route Map**

- Flight path with color-coded segments
- Satellite coverage overlays
- AAR window markers

**Page 3: Timeline Chart**

- Horizontal bar chart with three rows (X-Band, Ka, Ku)
- Color-coded blocks showing each system's status over time
- Vertical grid lines at 1-hour intervals

**Page 4: System Behavior**

- Table with row per system (X-Band, Ka, Ku)
- Columns: System Name, Total Nominal Time, Total Degraded Time, Root Cause,
  Crew Implications

---

## Troubleshooting

### Problem: "Route file is invalid"

**Causes:**

- File is not XML format (check extension is `.kml`)
- Missing `<LineString>` element (must have continuous path)
- Coordinates outside valid range (lat: -90 to +90, lon: -180 to +180)

**Solution:**

1. Open KML file in text editor
2. Search for `<LineString>` (must be present)
3. Check sample route: `simple-circular.kml` works 100% of the time
4. If repairing manually, validate at <https://validator.kml4earth.appspot.com>

---

### Problem: "Cannot add X transition at those coordinates"

**Cause:** Coordinates don't project to the route (distance > 100 km from
nearest waypoint).

**Solution:**

1. Verify coordinates are correct (use route map to click nearest waypoint)
2. Use waypoint coordinate, not estimated intersection
3. Check that route file includes your intended area

---

### Problem: "Timeline is all yellow/red"

**Cause:** Multiple overlapping constraints (e.g., Ka gap + X transition at same
time).

**Solution:**

1. Review timeline carefully—this is valid and important
2. If unexpected, check:
   - X transition timing (should be ±15 min only)
   - Ka coverage dates (coverage maps updated quarterly)
   - AAR window placement (may overlap with other degradation)
3. Contact mission planning if result seems wrong

---

### Problem: "Cannot export to PDF"

**Cause:** Browser JavaScript disabled or missing libraries.

**Solution:**

1. Enable JavaScript in browser settings
2. Try Chrome/Chromium instead (most reliable)
3. Export CSV and open in spreadsheet to create manual PDF

---

## FAQ

**Q: What if I have both X transition AND Ka gap at the same time?** A: Status
becomes CRITICAL (red). This is rare but possible. Use Ka as primary during X
transition, keeping Ku as fallback.

**Q: How accurate are coverage maps?** A: Ka and Ku coverage updated quarterly.
Predictions valid within ±5 minutes (weather/propagation effects not modeled).

**Q: Can I add multiple AAR windows?** A: Yes, click **Add AAR Window** multiple
times. Each blocks X-Band independently.

**Q: What timezone should I use in export?** A: Crew uses Eastern (local +
DST-aware). Controllers use UTC. System outputs both in exports.

**Q: How long does planning take?** A: 5-10 minutes per mission (routes,
transports, AAR windows). Timeline computation instant.

---

## Support

For questions or issues:

1. Check **Troubleshooting** section above
2. Review timeline chart (most questions answered by visual inspection)
3. Contact mission operations with mission name + timestamp

---

## Related Documents

- **MISSION-COMM-SOP.md** — Operations playbook for monitoring and alert
  response
- **METRICS.md** — Prometheus metrics reference for dashboard integration
- **API-REFERENCE.md** — Mission planning API endpoints (for integrations)
