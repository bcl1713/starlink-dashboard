# API Common Types

[Back to API Reference](../README.md) | [Models Index](./README.md)

---

## Coordinate Types

All geographic coordinates use decimal degrees:

```typescript
latitude: float; // -90 to 90 (negative = South)
longitude: float; // -180 to 180 (negative = West)
altitude: float; // Meters above sea level
```

### Coordinate Validation

- `latitude`: Must be between -90 and 90
- `longitude`: Must be between -180 and 180
- `altitude`: No strict bounds (can be negative for below sea level)

---

## Timestamp Format

All timestamps use ISO-8601 format in UTC:

```text
"2025-10-31T10:30:00.000000"
```

---

## Distance Units

- Distances: meters (convert to km by dividing by 1000)
- Speed: knots
- Altitude: meters

---

## Validation Rules

### Name Validation

- POI names must be unique
- Names cannot be empty strings
- Maximum length typically 255 characters

### Speed Validation

- Speed must be non-negative
- Typical range: 0-500 knots
- Speed of 0 indicates stationary

### Percentage Validation

- All percentages must be between 0 and 100
- Includes: obstruction_percent, signal_quality_percent, packet_loss_percent,
  progress_percent

---

[Back to API Reference](../README.md) | [Models Index](./README.md)
