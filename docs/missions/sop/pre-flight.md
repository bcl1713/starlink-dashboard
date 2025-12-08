# Pre-Flight Planning & Export Delivery

## Overview

This Standard Operating Procedure (SOP) guides mission operations teams to
**monitor communication status** during flight, respond to alerts, and ensure
crew connectivity through predicted degradation windows.

**Key Responsibilities:**

- **Pre-flight:** Validate timeline predictions
- **During-flight:** Monitor Grafana dashboards
- **Alert:** Respond to degradation warnings
- **Post-flight:** Document and archive mission results

**Success Criteria:**

- Crew receives X-Band/Ka/Ku status updates ≥ 15 min before predicted
  degradation
- All critical windows (2+ systems down) acknowledged within 5 minutes
- Mission timeline exported and delivered to stakeholders before departure

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
   - ✅ All segments show expected status
   - ❓ Any red (CRITICAL) segments? Escalate to mission planner
   - ✅ Export to PDF and share with crew briefing

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

## Export Delivery

### Pre-Flight Export

#### Delivery timeline: T-2 to T-1 day before flight

1. **Generate final timeline:**

```text
<http://localhost:8000/ui/mission-planner> → Select mission → Click "Export"
```

1. **Export all three formats:**
   - ✅ PDF: For crew briefing handout
   - ✅ Excel: For mission planning team analysis
   - ✅ CSV: For integration with flight ops database

2. **Filename convention:**

```text
mission-`name`-<departure-date>-<version>.pdf
mission-`name`-<departure-date>-<version>.xlsx
mission-`name`-<departure-date>-<version>.csv
```

Example: `mission-Leg6Rev6-2025-03-15-final.pdf`

1. **Delivery checklist:**
   - [ ] PDF printed and placed in crew briefing packet
   - [ ] Excel file emailed to mission planning (with notes on CRITICAL windows)
   - [ ] CSV loaded into mission tracking database
   - [ ] All stakeholders (flight lead, CNRC, air boss) acknowledge receipt
   - [ ] Version number updated if any changes made

### Post-Flight Archive

**After landing:**

1. **Capture final metrics:**

   ```bash
   curl <http://localhost:8000/api/missions/active/timeline>
   ```

   Save as `mission-`name`-<date>-actual-timeline.json`

1. **Compare predicted vs. actual:**
   - How close did predictions match?
   - Were there unexpected degradations?
   - Did crew respond effectively?

1. **Archive folder:**

   ```text
   /archive/missions/<year>/<month>/<mission-name>/
     ├── mission-brief.pdf
     ├── predicted-timeline.json
     ├── actual-timeline.json
     ├── grafana-screenshots/
     └── ops-log.txt
   ```

1. **Document lessons learned:**
   - Any timeline inaccuracies? Report to mission planner
   - Did alerts fire correctly? Note for future tuning
   - Crew feedback on comms plan? Archive for next flight
