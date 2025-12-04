# API Data Models Index

[Back to API Reference](../README.md) | [Back to main docs](../../INDEX.md)

---

## Overview

Complete data model reference for the Starlink Dashboard API, organized by
category.

---

## Model Categories

### [Common Types](./common-types.md)

Core types used across all endpoints:

- Coordinate types and validation
- Timestamp formats
- Distance units
- Validation rules

### [Health & Status Models](./health-status-models.md)

Service health and telemetry status:

- HealthResponse
- StatusResponse
- Position, Network, Obstruction
- Environmental data

### [POI Models](./poi-models.md)

Point of Interest data structures:

- POI (base model)
- POIWithETA (extended model)
- POICreateRequest
- POIUpdateRequest

### [Route Models](./route-models.md)

Route and geography models:

- RouteProgress
- RouteTimingProfile
- GeoJSON Feature Collection

### [Configuration Models](./configuration-models.md)

Service configuration structures:

- Configuration (main config)
- Route configuration
- Network configuration
- Obstruction configuration

### [ETA Models](./eta-models.md)

ETA calculation models:

- WaypointETA
- LocationETA
- ETACacheMetrics
- ETAAccuracyMetrics

---

## Quick Reference

**Most Common Models:**

- Status data: [StatusResponse](./health-status-models.md#statusresponse)
- POI with ETA: [POIWithETA](./poi-models.md#poiwitheta-extended-model)
- Route progress: [RouteProgress](./route-models.md#routeprogress)
- Service health: [HealthResponse](./health-status-models.md#healthresponse)

**Validation:**

- Coordinate rules: [Common Types](./common-types.md#coordinate-validation)
- Name rules: [Common Types](./common-types.md#name-validation)
- Percentage rules: [Common Types](./common-types.md#percentage-validation)

---

[Back to API Reference](../README.md) | [Back to main docs](../../INDEX.md)
