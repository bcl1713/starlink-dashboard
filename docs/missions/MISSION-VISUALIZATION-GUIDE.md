# Mission Visualization Guide

## Implementation Patterns for Map/Chart Generation

### 1. [Visual Data Models & Extraction](viz/DATA-MODELS.md)

Overview of the visual data model, timeline segment status hierarchy (Nominal,
Degraded, Critical), color mapping, and core data extraction patterns.

### 2. [Timeline to Route & Advisory Patterns](viz/MAPPING-PATTERNS.md)

Patterns for aligning timeline segments to geographic route points, overlaying
advisories on charts, and integrating Points of Interest (POIs).

### 3. [Data Extraction & Format Patterns](viz/EXTRACTION-PATTERNS.md)

Standard patterns for extracting timeline statistics, route geometry for
mapping, and consistent timezone formatting (UTC, Eastern, T-offset).

### 4. [Visualization Implementation & Logic](viz/IMPLEMENTATION.md)

Handling special cases (X-Ku conflicts, missing timing data), a complete data
flow example, and summary of key implementation takeaways.
