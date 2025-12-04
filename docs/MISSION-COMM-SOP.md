# Mission Communication Operations SOP

**Last Updated:** 2025-11-16 **Phase:** 5.3 (Comprehensive Documentation)
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Flight Planning](#pre-flight-planning)
3. [Grafana Monitoring Setup](#grafana-monitoring-setup)
4. [Alert Response](#alert-response)
5. [During Flight Operations](#during-flight-operations)
6. [Export Delivery](#export-delivery)
7. [Incident Response](#incident-response)

---

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

## Grafana Monitoring Setup

### 1. Access Grafana Dashboard

**Dashboard Location:**

```text
<http://<dashboard>/d/starlink/fullscreen-overview>
```

**Login:** admin / `<configured-password>` (default: admin)

### 2. Configure Mission Overview Panel

The dashboard auto-updates with mission metrics. Key panels:

#### Panel: Active Mission Status

- **What it shows:** Current mission name, activation status, timeline state
- **Metric:** `mission_is_active{mission_id="<id>"}`
- **Update interval:** 1 second

#### Panel: Communication Status (Real-time)

- **What it shows:** Current status of X-Band, Ka, Ku (green/yellow/red)
- **Metrics:**
  - `mission_status{transport="x_band"}`
  - `mission_status{transport="ka"}`
  - `mission_status{transport="ku"}`
- **Update interval:** 1 second
- **Action:** If any system shows red unexpectedly, check timeline and
  investigation log

#### Panel: Next Degradation Window

- **What it shows:** Time until next DEGRADED or CRITICAL status
- **Metric:** `mission_next_conflict_seconds`
- **Update interval:** 10 seconds
- **Action:** When < 900 sec (15 min), alert crew per section below

#### Panel: Metrics Gauges

- **Total Nominal Time (minutes):** Time remaining in NOMINAL status
- **Total Degraded Time (minutes):** Remaining degradation windows
- **Total Critical Time (minutes):** Remaining high-risk windows (usually 0)

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
- Action: Immediate escalation (see Alert Response below)

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

## Alert Response

### Alert Level 1: DEGRADED Window Approaching (Yellow)

**Trigger:** `mission_next_conflict_seconds{status="degraded"} < 900`

**Crew Notification (15 min before degradation):**

1. **Check timeline PDF:** Confirm predicted degradation type (X-Band? Ka? AAR?)
2. **Send crew message:**

```text
"COMM PLAN UPDATE: Degradation window T-15 minutes. [Description].
Primary system: [X-Band/Ka/Ku]. Secondary: [backup]. Confirm receipt."
```

1. **Verify crew acknowledges** (within 2 minutes)
2. **Log in mission journal:**

```text
14:10 UTC - Degradation alert issued for 14:25-14:40 window
14:12 UTC - Crew acknowledged (pilot confirmed Ka primary)
```

**Crew Actions (provided in briefing):**

- Reduce non-critical data usage
- Avoid large file transfers
- Keep voice comms ready (lower bandwidth)
- Monitor system status panel in aircraft

---

### Alert Level 2: CRITICAL Window Approaching (Red)

**Trigger:** `mission_next_conflict_seconds{status="critical"} < 900`

**Immediate Escalation (Priority: HIGH):**

1. **Ring out immediately:**
   - Flight Lead / Aircraft Commander
   - Mission Control Center (CNRC)
   - Air Boss (if applicable)

2. **Brief message:**

```text
"CRITICAL COMM ALERT: In [time], both X-Band and Ka will be degraded simultaneously
for [duration]. Aircraft will be on Ku only. Confirm readiness and mitigation plan."
```

1. **Crew Mitigation Options:**
   - **Option A (Default):** Continue on Ku (lower bandwidth, latency
     acceptable)
   - **Option B:** Delay flight departure by 30 min (reschedule window)
   - **Option C:** Reroute to avoid critical window (if feasible)

1. **Decision & Log:**
   - Ops Chief decides course of action
   - Log decision and reasoning:

```text
13:55 UTC - CRITICAL alert: Ka gap + X transition overlap 14:25-14:40
14:00 UTC - Ops Chief decision: Accept, crew briefed on Ku contingency
14:03 UTC - Flight Lead acknowledges mitigation plan
```

1. **Ongoing Monitoring (during window):**
   - Assign one operator to watch Grafana
   - If Ku also degrades unexpectedly: Emergency escalation (call Flight Lead
     immediately)
   - Ku should stay GREEN (always available) in timeline

---

## During Flight Operations

### Monitoring Routine

**Every 15 minutes (or per SOP interval):**

1. **Check Grafana dashboard:**
   - Current status: X-Band, Ka, Ku (should match timeline prediction)
   - Next degradation window (if < 30 min, send crew reminder)
   - Alert panel: Any red alerts firing?

2. **Cross-reference with timeline:**
   - If current status ≠ predicted: Investigate
   - Check system logs: `docker logs -f starlink-location | grep mission`
   - Document discrepancy and notify lead

3. **Log status snapshot** (every 30 min):

```text
15:30 UTC - Status: X-NOMINAL, Ka-NOMINAL, Ku-NOMINAL, Next-window@16:45
16:00 UTC - Status: X-NOMINAL, Ka-NOMINAL, Ku-NOMINAL, Next-window@16:45
16:30 UTC - Status: X-DEGRADED (transition), Ka-NOMINAL, Ku-NOMINAL
           Crew briefed, using Ka primary, expected to end 16:45
```

### Handling Unexpected Status Changes

#### Scenario: Timeline predicts NOMINAL, but dashboard shows DEGRADED

1. **Do not panic.** Timing discrepancies (±5 min) are normal.
1. **Check:**
   - Is window within ±5 min of predicted? If yes, normal drift.
   - Is it X-Band transition? Check transition duration (should be ±15 min).
   - Is it Ka gap? Check if route actually in coverage.
1. **If deviation > 10 min:**
   - Take screenshot of Grafana
   - Check system logs: `docker compose logs starlink-location | tail -50`
   - Contact mission planner with screenshot + crew observations
   - Continue monitoring (do not abort)

#### Scenario: Timeline shows one system down, but crew reports both down

1. **Inform Ops Chief immediately.**
1. **Get crew details:**
   - Which systems unavailable? (X? Ka? Both?)
   - Any error messages?
   - Current aircraft position (lat/lon)?
1. **Verify against timeline:**
   - Is this a CRITICAL window? (If yes, explain Ku should be available)
   - Check Prometheus metric: `mission_status{transport="ku"}`
1. **Action:**
   - If Ku also degraded: Escalate to System Ops (possible infrastructure issue)
   - If Ku working: Advise crew to check antenna selection, restart comms
     equipment

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

---

## Incident Response

### Incident: Unexpected Degradation

**Definition:** System(s) degrade outside predicted window or for longer than
predicted.

**Detection:**

- Crew reports comms loss
- Dashboard shows RED/DEGRADED unexpectedly
- Timeline shows no corresponding window

**Response (Immediate - 0-5 min):**

1. **Get incident details:**

   - What time did loss occur? (UTC)
   - Which system(s) affected? (X/Ka/Ku)
   - How long did it last?
   - Any error messages at aircraft?
   - Aircraft position (lat/lon) if available

1. **Check Grafana & logs:**

   ```bash
   # Check Prometheus for anomalies
   curl '<http://localhost:9090/api/v1/query?query=mission_status'>

   # Check backend logs for errors
   docker logs starlink-location | grep -i error | tail -20
   ```

1. **Consult timeline:**
   - Is incident within any predicted DEGRADED window?
   - Is it within ±10 min of predicted window?
   - If neither: Escalate (possible infrastructure failure)

**Response (Follow-up - 5-30 min):**

1. **Notify stakeholders:**

   - Flight Lead (situation update)
   - Ops Chief (decision on continue vs. contingency)
   - Mission Planner (event for investigation)

1. **Provide crew with:**

   - Next time system should recover (if predictable)
   - Backup system status (Ku should always be available)
   - Instructions if incident affects mission (e.g., delay non-critical work)

1. **Log incident:**

```text
14:25 UTC - INCIDENT: X-Band and Ka both lost, crew reports no signal
14:26 UTC - Checked: Timeline predicted X-transition 14:25-14:40, within window
14:27 UTC - Confirmed with crew: They received pre-briefing, expected window
14:28 UTC - System recovered as predicted, crew confirmed Ka available
14:30 UTC - Status: RESOLVED. Incident was within predicted timeline, no action needed
```

### Incident: Equipment Failure

**Definition:** System becomes unavailable outside normal predictions (e.g.,
transmitter hardware failure).

**Detection:**

- Dashboard shows system stuck in DEGRADED/RED
- Status doesn't recover after predicted window ends
- Crew unable to establish connection despite timeline showing available

**Immediate Response (0-5 min):**

1. **Declare emergency:** Contact Ops Chief / Flight Lead
1. **Get crew status:** Are they safe? Do they need emergency comms?
1. **Check which system failed:**
   - If **X-Band or Ka fails:** Crew routes to Ku (should be available)
   - If **Ku fails:** Emergency (all systems down)

**Analysis & Escalation (5-30 min):**

1. **Check infrastructure logs:**

   ```bash
   docker compose logs > /tmp/incident-$(date +%s).log
   # Send to system engineer
   ```

1. **Verify metrics:**

   ```bash
   curl <http://localhost:8000/metrics> | grep mission
   ```

1. **Escalate to:**
   - System Operations (infrastructure investigation)
   - Mission Planner (next-flight impact analysis)
   - Flight Safety (incident report)

**Recovery:**

1. **Restart services if safe:**

   ```bash
   docker compose down
   docker compose up -d
   # Verify mission re-activates and metrics resume
   ```

1. **Verify crew comms restored:**

   - Dashboard shows system NOMINAL
   - Crew confirms signal and data rates normal

1. **Post-incident review:**
   - Root cause analysis (hardware? software? config?)
   - Design improvements (redundancy? failover?)
   - Documentation update (incident log, lessons learned)

---

## Appendix A: Quick Reference Card

**Pre-Flight (T-2 days):**

1. Generate timeline (mission planner)
2. Identify risk windows (CRITICAL: escalate)
3. Export PDF, Excel, CSV
4. Deliver to crew + stakeholders

**During Flight:**

1. Monitor Grafana every 15 min
1. Match dashboard to timeline predictions
1. Alert crew 15 min before any degradation
1. Log status snapshots every 30 min

**Post-Flight:**

1. Archive actual timeline
1. Compare to predictions (notes for planner)
1. Document lessons learned
1. Close mission

---

## Appendix B: Useful URLs

| Resource           | URL                                                        |
| ------------------ | ---------------------------------------------------------- |
| Mission Planner    | `<http://<dashboard>/ui/mission-planner`>                  |
| Grafana Dashboard  | `<http://<dashboard>:3000/d/starlink/fullscreen-overview`> |
| Prometheus Metrics | `<http://<dashboard>:9090`>                                |
| API Documentation  | `<http://<dashboard>:8000/docs`>                           |
| Health Check       | `<http://<dashboard>:8000/health`>                         |

---

## Appendix C: Contact Information

- **Mission Planner Lead:** [Name, Phone, Email]
- **Ops Chief:** [Name, Phone, Email]
- **System Engineer:** [Name, Phone, Email]
- **Flight Safety Officer:** [Name, Phone, Email]

---

**Document Version:** 1.0 **Effective Date:** 2025-11-16 **Next Review:**
2026-02-16
