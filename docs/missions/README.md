# Mission Planning Documentation

This directory contains comprehensive documentation for the Mission Planning
feature set.

---

## Documentation Files

### Planning & Operations

- **[PLANNING-guide.md](./mission-planning-guide.md)** (470 lines) - Complete
  mission planning guide
- **[COMM-SOP.md](./mission-comm-sop.md)** (562 lines) - Communication standard
  operating procedures
- **[VISUALIZATION-guide.md](./mission-visualization-guide.md)** (573 lines) -
  Dashboard visualization guide
- **[V2 acceptance contract](./v2-mission-retirement-acceptance.md)** - Public
  controls and visible Mission V2 activation journey

### Data Reference

- **[DATA-STRUCTURES.md](./mission-data-structures.md)** (526 lines) - Complete
  data structure reference
- **[DATA-STRUCTURES-index.md](./mission-data-structures-index.md)** (275 lines)
  - Quick index
- **[DATA-QUICK-reference.md](./mission-data-quick-reference.md)** (213 lines) -
  Quick reference guide

---

## Quick Overview

The Mission Planning feature enables:

- **Flight Planning:** Define routes with waypoints and timing
- **Communication Planning:** Satellite coverage and timeline analysis
- **Real-time Monitoring:** Track mission progress and ETAs
- **Data Export:** Generate comprehensive mission reports

### Key Capabilities

| Feature            | Description                                    |
| ------------------ | ---------------------------------------------- |
| **Route Planning** | KML import, waypoint management                |
| **Timeline**       | Communication windows, conflict detection      |
| **Satellite**      | Coverage overlay, transport analysis, tracking |
| **Visualization**  | Grafana dashboards, real-time maps             |
| **Export**         | PDF, PowerPoint, Excel, CSV formats            |

### Mission V2 activation

Mission activation is performed only through:

```text
POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate
```

`/api/missions` has been removed and now returns 404; it has no supported
operator or API commands. Active legs retain their route binding on full-leg
`PUT`; use deactivate → route replacement → activate to change a route. To
delete an active leg or a mission with active legs, deactivate first, then
repeat the delete request.

### Legacy data boundary

Flat v1 mission artifacts are retained but inert. They have no automatic
migration or cleanup, and they do not establish Mission V2 activation or
Overview context. Preserve them as historical files until an explicitly
approved retention action is defined.

---

## Documentation Index

### For New Users

1. Start with **[PLANNING-guide.md](./mission-planning-guide.md)**
2. Review **[DATA-QUICK-reference.md](./mission-data-quick-reference.md)**
3. Set up visualization with
   **[VISUALIZATION-guide.md](./mission-visualization-guide.md)**

### For Operators

1. Follow **[COMM-SOP.md](./mission-comm-sop.md)** for operational procedures
2. Reference **[DATA-STRUCTURES-index.md](./mission-data-structures-index.md)**
   for quick lookups

### For Developers

1. Study **[DATA-STRUCTURES.md](./mission-data-structures.md)** for complete API
   reference
2. Review architecture in
   **[../architecture/README.md](../architecture/README.md)**

---

[Back to main docs](../index.md)
