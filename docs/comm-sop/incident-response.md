# Incident Response

This document provides comprehensive procedures for handling communication
system incidents during mission operations.

---

## Incident: Unexpected Degradation

**Definition:** System(s) degrade outside predicted window or for longer than
predicted.

### Unexpected Degradation Detection

- Crew reports comms loss
- Dashboard shows RED/DEGRADED unexpectedly
- Timeline shows no corresponding window

### Response (Immediate - 0-5 min)

1. **Get incident details:**
   - What time did loss occur? (UTC)
   - Which system(s) affected? (X/Ka/Ku)
   - How long did it last?
   - Any error messages at aircraft?
   - Aircraft position (lat/lon) if available

2. **Check Grafana & logs:**

   ```bash
   # Check Prometheus for anomalies
   curl '<http://localhost:9090/api/v1/query?query=mission_status'>
   # (truncated for brevity)

   # Check backend logs for errors
   docker logs starlink-location | rg -i error | tail -20
   ```

3. **Consult timeline:**
   - Is incident within any predicted DEGRADED window?
   - Is it within ±10 min of predicted window?
   - If neither: Escalate (possible infrastructure failure)

### Response (Follow-up - 5-30 min)

1. **Notify stakeholders:**
   - Flight Lead (situation update)
   - Ops Chief (decision on continue vs. contingency)
   - Mission Planner (event for investigation)

2. **Provide crew with:**
   - Next time system should recover (if predictable)
   - Backup system status (Ku should always be available)
   - Instructions if incident affects mission (e.g., delay non-critical work)

3. **Log incident:**

   ```text
   14:25 UTC - INCIDENT: X-Band and Ka both lost, crew reports no signal
   14:26 UTC - Checked: Timeline predicted X-transition 14:25-14:40,
               within window
   14:27 UTC - Confirmed with crew: They received pre-briefing,
               expected window
   14:28 UTC - System recovered as predicted, crew confirmed Ka available
   14:30 UTC - Status: RESOLVED. Incident was within predicted timeline,
               no action needed
   ```

---

## Incident: Equipment Failure

**Definition:** System becomes unavailable outside normal predictions (e.g.,
transmitter hardware failure).

### Equipment Failure Detection

- Dashboard shows system stuck in DEGRADED/RED
- Status doesn't recover after predicted window ends
- Crew unable to establish connection despite timeline showing available

### Immediate Response (0-5 min)

1. **Declare emergency:** Contact Ops Chief / Flight Lead
2. **Get crew status:** Are they safe? Do they need emergency comms?
3. **Check which system failed:**
   - If **X-Band or Ka fails:** Crew routes to Ku (should be available)
   - If **Ku fails:** Emergency (all systems down)

### Analysis & Escalation (5-30 min)

1. **Check infrastructure logs:**

   ```bash
   docker compose logs > /tmp/incident-$(date +%s).log
   # Send to system engineer
   ```

2. **Verify metrics:**

   ```bash
   curl <http://localhost:8000/metrics> | rg mission
   ```

3. **Escalate to:**
   - System Operations (infrastructure investigation)
   - Mission Planner (next-flight impact analysis)
   - Flight Safety (incident report)

### Recovery

1. **Restart services if safe:**

   ```bash
   docker compose down
   docker compose up -d
   # Verify mission re-activates and metrics resume
   ```

2. **Verify crew comms restored:**
   - Dashboard shows system NOMINAL
   - Crew confirms signal and data rates normal

3. **Post-incident review:**
   - Root cause analysis (hardware? software? config?)
   - Design improvements (redundancy? failover?)
   - Documentation update (incident log, lessons learned)

---

## Emergency Contact Procedures

### Communication Failure Emergency

If all communication systems fail:

1. **Immediate Actions (0-2 min):**
   - Declare emergency to Ops Chief
   - Notify Flight Safety Officer
   - Activate emergency communication protocol

2. **Crew Instructions:**
   - Follow emergency comm procedures in flight manual
   - Attempt alternate communication methods
   - Continue mission per safety protocols

3. **Ground Support:**
   - Monitor all available tracking systems
   - Prepare for emergency landing support if needed
   - Maintain continuous situation updates

### Escalation Tree

```text
Level 1 → Mission Control Operator
         ↓ (if unresolved in 5 min)
Level 2 → Ops Chief
         ↓ (if critical or unresolved in 15 min)
Level 3 → Flight Safety Officer + System Engineer
         ↓ (if emergency or safety concern)
Level 4 → Executive Leadership + Emergency Response Team
```

---

## Incident Log Template

```text
INCIDENT LOG - [Mission Name] - [Date]

[HH:MM UTC] - Initial report: [description]
[HH:MM UTC] - Action: [what was done]
[HH:MM UTC] - Observation: [result]
[HH:MM UTC] - Status update: [current state]
[HH:MM UTC] - Resolution: [how resolved]

Final Status: [RESOLVED/ONGOING/ESCALATED]
Follow-up Required: [YES/NO]
Post-Incident Review Scheduled: [DATE/TIME]
```

---

## Additional Documentation

For detailed post-incident review procedures and severity levels, see:

- [Incident Severity Levels](incident-severity-levels.md)
- [Post-Incident Review](post-incident-review.md)
