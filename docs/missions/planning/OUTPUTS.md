# Mission Export Formats

## Export Formats

### CSV Export

**File:** `mission-`name`-<timestamp>.csv`

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

**File:** `mission-`name`-<timestamp>.xlsx`

### Sheet 1: Summary

- Geographic map showing mission route with color-coded segments (green=NOMINAL,
  yellow=DEGRADED, red=CRITICAL)
- Map resolution: 3840×2880 pixels @ 300 DPI (12.8" × 9.6" for printing)
- Labeled markers for departure airport (blue), arrival airport (purple), and
  mission-event POIs (orange)
- Route centered with 5% smart padding (5% on larger dimension, other dimension
  auto-adjusted for aspect ratio)
- Horizontal timeline bar chart showing X-Band, Ka, and Ku transport states over
  time
- Simplified summary table with columns: Start (UTC), Duration, Status, Systems
  Down
- Color-coded table rows matching segment status

### Sheet 2: Detailed Breakdown

- All three time zones (UTC, Eastern, T+)
- System-by-system status per segment
- Notes column for manual annotations

### Sheet 3: Statistics

- Total mission duration
- Nominal time / Degraded time / Critical time (hours and percentage)
- System availability chart (X-Band %, Ka %, Ku %)
- Risk assessment summary

---

### PDF Export

**File:** `mission-`name`-<timestamp>.pdf`

### Page 1: Executive Summary

- Mission name, date, route overview
- Key statistics (total time, degradation windows)
- Risk rating (Green/Yellow/Red)

### Page 2: Route Map

- Flight path with color-coded segments
- Satellite coverage overlays
- AAR window markers

### Page 3: Timeline Chart

- Horizontal bar chart with three rows (X-Band, Ka, Ku)
- Color-coded blocks showing each system's status over time
- Vertical grid lines at 1-hour intervals

### Page 4: System Behavior

- Table with row per system (X-Band, Ka, Ku)
- Columns: System Name, Total Nominal Time, Total Degraded Time, Root Cause,
  Crew Implications
