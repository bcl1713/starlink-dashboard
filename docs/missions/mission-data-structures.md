<!-- markdownlint-disable-file MAX_LINES -->

# Mission Data Structures Reference

## For Map and Chart Generation in Mission Exporter

---

## Reference Sections

### 1. [Core Mission Models & Enums](data/models.md)

Defines Mission, MissionTimeline, TimelineSegment, TimelineAdvisory, and related
Pydantic models and Enums used throughout the system.

### 2. [Route & POI Data Structures](data/routes-pois.md)

Details the ParsedRoute (metadata, points, waypoints) and POI (Points of
Interest, including real-time ETA) structures essential for map visualization.

### 3. [Exporter Helper Functions](data/exporter-helpers.md)

Documentation for the helper functions in exporter.py, including color
constants, timestamp formatting, transport display mapping, and DataFrame
generation helpers.

### 4. [Data Flow & Implementation Notes](data/implementation-notes.md)

Step-by-step data flows for generating maps and charts, plus critical
implementation notes regarding timezone handling, duration formatting, and route
integration.
