# Pre-Flight Planning Procedures

This document covers all pre-flight planning procedures for mission
communications monitoring and management.

---

## Pre-Flight Planning

### 1. Generate Mission Timeline

#### Timeline Creation (T-5 to T-2 days before flight)

1. Open mission planner: the configured Mission Planner frontend
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

### 3. Verify alert coverage

The repository includes example mission alert rules, but their `status` label
filters do not match the current `mission_next_conflict_seconds` metric, which
has only `mission_id`. Do not assume these rules will fire or notify crew.
Review actual metric labels and deployed rules with the monitoring owner and use
scheduled manual timeline checks until alert delivery is verified. Prometheus
rule evaluation alone does not send a crew notification.

## Export delivery

Prepare the mission export through the Missions page on the configured frontend
origin (development default <http://localhost:5173>). Review the ready package's
PDF and timeline artifacts before briefing the crew. See
[export preparation](../missions/planning/outputs.md). Archive the package with
the mission identifier, source revision and briefing date using your team's
approved document channel. Sharing and crew acknowledgement are operator tasks.
