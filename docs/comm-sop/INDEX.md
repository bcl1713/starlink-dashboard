# Mission Communication Operations SOP

**Last Updated:** 2025-11-16
**Phase:** 5.3 (Comprehensive Documentation)
**Status:** Production Ready

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

## Documentation Contents

This SOP is organized into the following sections:

### [Operations Procedures](operations-procedures.md)

Complete operational procedures for mission communications:

- **Pre-Flight Planning** - Timeline generation, risk window identification, crew
  briefing
- **Grafana Monitoring Setup** - Dashboard configuration, panel descriptions,
  alert thresholds
- **Alert Response** - Degraded and critical window response procedures
- **During Flight Operations** - Monitoring routine, handling unexpected changes
- **Export Delivery** - Pre-flight and post-flight export procedures

### [Incident Response](incident-response.md)

Comprehensive incident handling procedures:

- **Unexpected Degradation** - Detection, immediate response, follow-up
- **Equipment Failure** - Emergency response, analysis, escalation, recovery
- **Post-Incident Review** - Root cause analysis, documentation, lessons learned

---

## Quick Reference Card

### Pre-Flight (T-2 days)

1. Generate timeline (mission planner)
2. Identify risk windows (CRITICAL: escalate)
3. Export PDF, Excel, CSV
4. Deliver to crew + stakeholders

### During Flight

1. Monitor Grafana every 15 min
2. Match dashboard to timeline predictions
3. Alert crew 15 min before any degradation
4. Log status snapshots every 30 min

### Post-Flight

1. Archive actual timeline
2. Compare to predictions (notes for planner)
3. Document lessons learned
4. Close mission

---

## Useful URLs

| Resource           | URL                                     |
| ------------------ | --------------------------------------- |
| Mission Planner    | `http://<dashboard>/ui/mission-planner` |
| Grafana Dashboard  | `http://<dashboard>:3000/d/starlink/*`  |
| Prometheus Metrics | `http://<dashboard>:9090`               |
| API Documentation  | `http://<dashboard>:8000/docs`          |
| Health Check       | `http://<dashboard>:8000/health`        |

(* = fullscreen-overview)

---

## Contact Information

- **Mission Planner Lead:** [Name, Phone, Email]
- **Ops Chief:** [Name, Phone, Email]
- **System Engineer:** [Name, Phone, Email]
- **Flight Safety Officer:** [Name, Phone, Email]

---

**Document Version:** 1.0
**Effective Date:** 2025-11-16
**Next Review:** 2026-02-16
