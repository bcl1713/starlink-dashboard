# Incident Response & Appendices

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
