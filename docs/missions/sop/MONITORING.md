# Monitoring & Alert Response

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
   - If Ku also degraded unexpectedly: Emergency escalation (call Flight Lead
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
