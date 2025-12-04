# Mission Planning Documentation

This directory contains comprehensive documentation for the Mission Planning
feature set.

---

## Documentation Files

### Planning & Operations

- **[PLANNING-GUIDE.md](./MISSION-PLANNING-GUIDE.md)** (470 lines) - Complete
  mission planning guide
- **[COMM-SOP.md](./MISSION-COMM-SOP.md)** (562 lines) - Communication standard
  operating procedures
- **[VISUALIZATION-GUIDE.md](./MISSION-VISUALIZATION-GUIDE.md)** (573 lines) -
  Dashboard visualization guide

### Data Reference

- **[DATA-STRUCTURES.md](./MISSION-DATA-STRUCTURES.md)** (526 lines) - Complete
  data structure reference
- **[DATA-STRUCTURES-INDEX.md](./MISSION-DATA-STRUCTURES-INDEX.md)** (275 lines)
  - Quick index
- **[DATA-QUICK-REFERENCE.md](./MISSION-DATA-QUICK-REFERENCE.md)** (213 lines) -
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

### Quick Start

```bash
# Create a mission
curl -X POST http://localhost:8000/api/missions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Flight",
    "departure_time": "2025-12-04T10:00:00Z",
    "arrival_time": "2025-12-04T18:00:00Z"
  }'

# Upload route
curl -X POST http://localhost:8000/api/routes/upload \
  -F "file=@flight-route.kml"

# Activate mission
curl -X POST http://localhost:8000/api/missions/{id}/activate
```

---

## Documentation Index

### For New Users

1. Start with **[PLANNING-GUIDE.md](./MISSION-PLANNING-GUIDE.md)**
2. Review **[DATA-QUICK-REFERENCE.md](./MISSION-DATA-QUICK-REFERENCE.md)**
3. Set up visualization with
   **[VISUALIZATION-GUIDE.md](./MISSION-VISUALIZATION-GUIDE.md)**

### For Operators

1. Follow **[COMM-SOP.md](./MISSION-COMM-SOP.md)** for operational procedures
2. Reference **[DATA-STRUCTURES-INDEX.md](./MISSION-DATA-STRUCTURES-INDEX.md)**
   for quick lookups

### For Developers

1. Study **[DATA-STRUCTURES.md](./MISSION-DATA-STRUCTURES.md)** for complete API
   reference
2. Review architecture in
   **[../architecture/README.md](../architecture/README.md)**

---

[Back to main docs](../INDEX.md)
