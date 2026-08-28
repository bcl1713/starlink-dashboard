<!-- markdownlint-disable-file MAX_LINES -->

# Mission Data Structures Reference

## For Map and Chart Generation in Mission Exporter

---

## Reference Sections

### 1. [Core Mission and Timeline Models](../data-structures/mission-timeline-models.md)

Defines Mission, MissionLegTimeline, TimelineSegment, TimelineAdvisory, and
transport configuration models used throughout the system.

### 2. [Route & POI Data Structures](../data-structures/route-poi-models.md)

Details the ParsedRoute (metadata, points, waypoints) and POI (Points of
Interest, including real-time ETA) structures essential for map visualization.

### 3. [Exporter Helper Functions](../mission-data/helper-functions.md)

Documents exporter color constants, timestamp formatting, transport display
mappings, and DataFrame generation helpers.

### 4. [Data Flow & Implementation Notes](viz/implementation.md)

Covers map and chart generation data flow, timezone handling, missing route
timing, and visualization edge cases.
