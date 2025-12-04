# Mission and Timeline Models

This document describes the core data structures for mission planning and
timeline generation.

---

## Mission Model

**Location:** `backend/starlink-location/app/mission/models.py`

### Mission Fields

```python
class Mission(BaseModel):
    id: str                              # Unique mission identifier
    name: str                            # Human-readable name
    description: Optional[str]           # Detailed description
    route_id: str                        # Associated flight route ID
    transports: TransportConfig          # Transport/satellite configuration
    created_at: datetime                 # Creation timestamp (UTC)
    updated_at: datetime                 # Last update timestamp (UTC)
    is_active: bool                      # Currently active flag
    notes: Optional[str]                 # Planner notes
```

### Key Relationships

- **route_id** → Links to a ParsedRoute (via route manager)
- **transports** → Contains transport configuration with satellite transitions

---

## MissionTimeline Model

**Location:** `backend/starlink-location/app/mission/models.py`

### MissionTimeline Fields

```python
class MissionTimeline(BaseModel):
    mission_id: str                      # Associated mission ID
    created_at: datetime                 # When timeline was computed (UTC)
    segments: list[TimelineSegment]      # Ordered timeline segments
    advisories: list[TimelineAdvisory]   # Operator advisories
    statistics: dict                     # Summary statistics
```

### Statistics Dict Keys

```python
{
    "total_duration_seconds": float,     # Total mission duration
    "nominal_seconds": float,            # Time with all transports available
    "degraded_seconds": float,           # One transport unavailable
    "critical_seconds": float,           # Two+ transports unavailable
    "_aar_blocks": list[dict]            # AAR windows (internal, starts with _)
}
```

---

## TimelineSegment Model

**Location:** `backend/starlink-location/app/mission/models.py`

### TimelineSegment Fields

```python
class TimelineSegment(BaseModel):
    id: str                              # Unique segment identifier
    start_time: datetime                 # Segment start (UTC, ISO-8601)
    end_time: datetime                   # Segment end (UTC, ISO-8601)
    status: TimelineStatus               # Overall communication status
    x_state: TransportState              # X-Band transport state
    ka_state: TransportState             # Ka (CommKa) transport state
    ku_state: TransportState             # Ku (StarShield) transport state
    reasons: list[str]                   # Reason codes explaining status
    impacted_transports: list[Transport] # Transports that are degraded/offline
    metadata: dict                       # Additional context
```

### Metadata Dict Structure

```python
{
    "satellites": {
        "X": "X-1" or "X-2",            # Current X-Band satellite
        "Ka": ["AOR", "POR", "IOR"]     # Current Ka satellites
    },
    # Additional context keys may vary
}
```

---

## TimelineAdvisory Model

**Location:** `backend/starlink-location/app/mission/models.py`

### TimelineAdvisory Fields

```python
class TimelineAdvisory(BaseModel):
    id: str                              # Unique advisory identifier
    timestamp: datetime                  # When advisory applies (UTC)
    event_type: str
    # e.g., "transition", "azimuth_conflict", "buffer", "aar_window"
    transport: Transport                 # X, Ka, or Ku
    severity: str                        # "info", "warning", or "critical"
    message: str                         # Human-readable advisory message
    metadata: dict
    # Additional context (satellite IDs, reason codes, etc.)
```

### Advisory Metadata Example

```python
{
    "reason": "transition",
    "satellite_from": "X-1",
    "satellite_to": "X-2",
    "buffer_minutes": 15,
}
```

---

## TransportConfig Model

**Location:** `backend/starlink-location/app/mission/models.py`

### TransportConfig Fields

```python
class TransportConfig(BaseModel):
    initial_x_satellite_id: str          # Initial X satellite (e.g., "X-1")
    initial_ka_satellite_ids: list[str]
    # Initial Ka satellites (e.g., ["AOR", "POR", "IOR"])
    x_transitions: list[XTransition]     # Satellite transitions on X
    ka_outages: list[KaOutage]           # Manual Ka outage windows
    aar_windows: list[AARWindow]         # Air-refueling segments
    ku_overrides: list[KuOutageOverride]
    # Manual Ku outage overrides
```

### XTransition Fields

```python
class XTransition(BaseModel):
    id: str                              # Unique transition identifier
    latitude: float                      # Actual transition latitude
    longitude: float                     # Actual transition longitude
    target_satellite_id: str
    # Target satellite ID (e.g., "X-1", "X-2")
    target_beam_id: Optional[str]        # Optional target beam ID
    is_same_satellite_transition: bool
    # True if different beam, same satellite
```
