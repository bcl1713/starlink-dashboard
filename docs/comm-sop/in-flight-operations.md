# In-Flight Operations and Alert Response

This document covers operational procedures during flight and alert response
protocols.

---

## Alert Response

### Alert Level 1: DEGRADED Window Approaching (Yellow)

**Trigger:** `mission_next_conflict_seconds{status="degraded"} < 900`

**Crew Notification (15 min before degradation):**

1. **Check timeline PDF:** Confirm predicted degradation type (X-Band? Ka? AAR?)
2. **Send crew message:**

   ```text
   COMM PLAN UPDATE: Degradation window T-15 minutes. [Description].
   Primary system: [X-Band/Ka/Ku]. Secondary: [backup]. Confirm receipt.
   ```

3. **Verify crew acknowledges** (within 2 minutes)
4. **Log in mission journal:**

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
   CRITICAL COMM ALERT: In [time], both X-Band and Ka will be degraded
   simultaneously for [duration]. Aircraft will be on Ku only.
   Confirm readiness and mitigation plan.
   ```

3. **Crew Mitigation Options:**
   - **Option A (Default):** Continue on Ku (lower bandwidth, latency
     acceptable)
   - **Option B:** Delay flight departure by 30 min (reschedule window)
   - **Option C:** Reroute to avoid critical window (if feasible)

4. **Decision & Log:**
   - Ops Chief decides course of action
   - Log decision and reasoning:

     ```text
     13:55 UTC - CRITICAL alert: Ka gap + X transition overlap 14:25-14:40
     14:00 UTC - Ops Chief decision: Accept, crew briefed on Ku contingency
     14:03 UTC - Flight Lead acknowledges mitigation plan
     ```

5. **Ongoing Monitoring (during window):**
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
2. **Check:**
   - Is window within ±5 min of predicted? If yes, normal drift.
   - Is it X-Band transition? Check transition duration (should be ±15 min).
   - Is it Ka gap? Check if route actually in coverage.
3. **If deviation > 10 min:**
   - Take screenshot of Grafana
   - Check system logs: `docker compose logs starlink-location | tail -50`
   - Contact mission planner with screenshot + crew observations
   - Continue monitoring (do not abort)

#### Scenario: Timeline shows one system down, but crew reports both down

1. **Inform Ops Chief immediately.**
2. **Get crew details:**
   - Which systems unavailable? (X? Ka? Both?)
   - Any error messages?
   - Current aircraft position (lat/lon)?
3. **Verify against timeline:**
   - Is this a CRITICAL window? (If yes, explain Ku should be available)
   - Check Prometheus metric: `mission_status{transport="ku"}`
4. **Action:**
   - If Ku also degraded: Escalate to System Ops (possible infrastructure issue)
   - If Ku working: Advise crew to check antenna selection, restart comms
     equipment

---

## Post-Flight Archive

**After landing:**

1. **Capture final metrics:**

   ```bash
   curl <http://localhost:8000/api/missions/active/timeline>
   ```

   Save as `mission-`name`-<date>-actual-timeline.json`

2. **Compare predicted vs. actual:**
   - How close did predictions match?
   - Were there unexpected degradations?
   - Did crew respond effectively?

3. **Archive folder:**

   ```text
   /archive/missions/<year>/<month>/<mission-name>/
     ├── mission-brief.pdf
     ├── predicted-timeline.json
     ├── actual-timeline.json
     ├── grafana-screenshots/
     └── ops-log.txt
   ```

4. **Document lessons learned:**
   - Any timeline inaccuracies? Report to mission planner
   - Did alerts fire correctly? Note for future tuning
   - Crew feedback on comms plan? Archive for next flight
