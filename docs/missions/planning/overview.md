# Mission Planning Overview & Workflow

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
   `<http://<dashboard-url>/ui/mission-planner`>
1. The interface loads a four-step form
1. You do **not** need Grafana or Prometheus experience—the planner is
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
