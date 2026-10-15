# Pre-Flight Planning Procedures

This document covers all pre-flight planning procedures for mission
communications monitoring and management.

---

## Pre-Flight Planning

### 1. Generate Mission Timeline

#### Timeline Creation (T-5 to T-2 days before flight)

1. Open mission planner: `<http://<dashboard>/ui/mission-planner`>
2. Upload flight route (KML from flight planning)
3. Configure communication systems:
   - X-Band: Enter manual transitions (coordinates from flight plan)
   - Ka: Verify coverage for your route (auto-detected)
   - Ku: Accept default (always available)
4. If applicable, add AAR windows (start/end waypoints)
5. Click **Compute Timeline**
6. Review result:
   - All segments show expected status
   - Any red (CRITICAL) segments? Escalate to mission planner
   - Export to PDF and share with crew briefing

### 2. Identify Risk Windows

#### Analysis (T-2 to T-1 day)

Review exported timeline and identify:

| Window Type                | Threshold    | Action                       |
| -------------------------- | ------------ | ---------------------------- |
| CRITICAL (2+ systems down) | Any duration | Escalate to Ops Chief        |
| DEGRADED (1 system down)   | > 30 minutes | Brief crew on primary system |
| X-Band Transition          | 30 min total | Assign Ka as primary         |
| Ka Coverage Gap            | > 15 min     | Plan Ku usage                |

**Example flag:**

```text
CRITICAL window: 14:25-14:40 UTC (15 min)
Root cause: X-Band transition overlaps Ka coverage gap
Crew action: Defer non-critical comms; use Ku only if both X and Ka fail
Notify: CNRC, Flight Lead, Air Boss
```

### 3. Prepare Crew Briefing

#### Briefing (T-1 day)

1. Print/display mission timeline PDF
2. Highlight:
   - X-Band transition times (with ±15 min pre/post buffers)
   - Ka coverage gaps (if > 5 min)
   - AAR window times
3. Crew reads timeline and confirms understanding
4. Document crew sign-off: "**\_** (name) acknowledged comm plan on **\_**
   (date)"

---

## Mission Planner Monitoring Setup

Open the native dashboard at <http://localhost:5173> (or its configured proxy
origin). Use Overview for current position, upcoming POIs and network history,
and Missions for the active mission leg and timeline. Configuration controls
Overview visibility and history settings.

For supported fields and freshness rules, see the
[Overview features](../features/overview.md). Query additional metrics and alert
status directly in Prometheus; retired dashboard panels are no longer
provisioned.

### 3. Set Alert Thresholds

**Prometheus Alert Rules** (auto-configured)

Two alert rules fire automatically:

#### Alert 1: DegradedWindowApproaching

```yaml
expr: mission_next_conflict_seconds{status="degraded"} < 900
for: 1m
severity: warning
```

- Fires when degradation window < 15 min away
- Severity: **WARNING** (yellow in dashboard)
- Action: Notify crew, confirm Ka/Ku readiness

#### Alert 2: CriticalWindowApproaching

```yaml
expr: mission_next_conflict_seconds{status="critical"} < 900
for: 1m
severity: critical
```

- Fires when critical window (2+ systems down) < 15 min away
- Severity: **CRITICAL** (red in dashboard)
- Action: Immediate escalation (see Alert Response section)

### 4. View Alert History

**Alert Rule Status:**

1. Navigate to Prometheus: `<http://<dashboard>:9090`>
2. Go to **Alerts**
3. Look for:
   - `MissionDegradedWindowApproaching`
   - `MissionCriticalWindowApproaching`
4. Click rule name to see:
   - Fire time
   - Duration
   - Labels (mission_id, status, next_time)

---

## Export Delivery

### Pre-Flight Export

#### Delivery timeline: T-2 to T-1 day before flight

1. **Generate final timeline:**

   ```text
   <http://localhost:8000/ui/mission-planner> → Select mission → Click "Export"
   ```

2. **Export all three formats:**
   - PDF: For crew briefing handout
   - Excel: For mission planning team analysis
   - CSV: For integration with flight ops database

3. **Filename convention:**

   ```text
   mission-`name`-<departure-date>-<version>.pdf
   mission-`name`-<departure-date>-<version>.xlsx
   mission-`name`-<departure-date>-<version>.csv
   ```

   Example: `mission-Leg6Rev6-2025-03-15-final.pdf`

4. **Delivery checklist:**
   - [ ] PDF printed and placed in crew briefing packet
   - [ ] Excel file emailed to mission planning (with notes on CRITICAL windows)
   - [ ] CSV loaded into mission tracking database
   - [ ] All stakeholders (flight lead, CNRC, air boss) acknowledge receipt
   - [ ] Version number updated if any changes made
