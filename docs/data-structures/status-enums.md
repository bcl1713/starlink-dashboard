# Status Enums and Constants

This document describes the enumeration types and constants used throughout the
mission system.

---

## Enums

### TimelineStatus

```python
class TimelineStatus(str, Enum):
    NOMINAL = "nominal"      # All transports available
    DEGRADED = "degraded"    # One transport unavailable
    CRITICAL = "critical"    # Two or more transports unavailable
```

### TransportState

```python
class TransportState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    OFFLINE = "offline"
```

### Transport

```python
class Transport(str, Enum):
    X = "X"      # Fixed geostationary satellite
    KA = "Ka"    # Three geostationary satellites
    KU = "Ku"    # Always-on LEO constellation
```

### MissionPhase

```python
class MissionPhase(str, Enum):
    PRE_DEPARTURE = "pre_departure"
    IN_FLIGHT = "in_flight"
    POST_ARRIVAL = "post_arrival"
```

---

## Exporter Constants and Mappings

**Location:** `backend/starlink-location/app/mission/exporter.py`

### Color Constants (Lines 37-48)

```python
LIGHT_YELLOW = colors.Color(1.0, 1.0, 0.85)  # For degraded highlighting
LIGHT_RED = colors.Color(1.0, 0.85, 0.85)    # For critical highlighting
```

### Transport Display Mapping

```python
TRANSPORT_DISPLAY = {
    Transport.X: "X-Band",
    Transport.KA: "CommKa",
    Transport.KU: "StarShield",
}

STATE_COLUMNS = [
    "X-Band",      # TRANSPORT_DISPLAY[Transport.X]
    "CommKa",      # TRANSPORT_DISPLAY[Transport.KA]
    "StarShield",  # TRANSPORT_DISPLAY[Transport.KU]
]
```

---

## Additional Documentation

For detailed usage patterns and integration examples, see:

- [Data Flow Patterns](status-data-flow.md)
- [Integration Examples](status-integration-examples.md)
