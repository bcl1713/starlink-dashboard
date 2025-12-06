<!-- markdownlint-disable-file MAX_LINES -->

# Mission Visualization Guide

## Implementation Patterns for Map/Chart Generation

### 1. [Visual Data Models & Extraction](viz/data-models.md)

Overview of the visual data model, timeline segment status hierarchy (Nominal,
Degraded, Critical), color mapping, and core data extraction patterns.

### 2. [Timeline to Route & Advisory Patterns](viz/mapping-patterns.md)

Patterns for aligning timeline segments to geographic route points, overlaying
advisories on charts, and integrating Points of Interest (POIs).

### 3. [Data Extraction & Format Patterns](viz/extraction-patterns.md)

Standard patterns for extracting timeline statistics, route geometry for
mapping, and consistent timezone formatting (UTC, Eastern, T-offset).

### 4. [Visualization Implementation & Logic](viz/implementation.md)

Handling special cases (X-Ku conflicts, missing timing data), a complete data
flow example, and summary of key implementation takeaways.
