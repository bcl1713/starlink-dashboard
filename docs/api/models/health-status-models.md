# Health & Status Models

[Back to API Reference](../README.md) | [Models Index](./README.md)

---

## HealthResponse

Response from `/health` endpoint.

```json
{
  "status": "ok", // "ok" or "error"
  "uptime_seconds": 3600.5, // float
  "mode": "simulation", // "simulation" or "live"
  "version": "0.2.0", // string
  "timestamp": "2025-10-31T10:30:00.000000", // ISO-8601
  "message": "Service is healthy", // string
  "dish_connected": true // bool
}
```

**Fields:**

- `status`: Overall health status
- `uptime_seconds`: Time since service started
- `mode`: Operating mode (simulation or live)
- `version`: Backend version
- `timestamp`: Current server time
- `message`: Human-readable status message
- `dish_connected`: Whether connected to Starlink dish (live mode only)

---

## StatusResponse

Response from `/api/status` endpoint.

```json
{
  "timestamp": "2025-10-31T10:30:00.000000",
  "position": {
    "latitude": 40.7128,
    "longitude": -74.006,
    "altitude": 5000.0,
    "speed": 25.5,
    "heading": 45.0
  },
  "network": {
    "latency_ms": 45.2,
    "throughput_down_mbps": 125.3,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0.5
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 3600.5,
    "temperature_celsius": null
  }
}
```

---

## Position

```json
{
  "latitude": 40.7128, // float: -90 to 90
  "longitude": -74.006, // float: -180 to 180
  "altitude": 5000.0, // float: meters
  "speed": 25.5, // float: knots
  "heading": 45.0 // float: degrees (0=North)
}
```

---

## Network

```json
{
  "latency_ms": 45.2, // float: milliseconds
  "throughput_down_mbps": 125.3, // float: megabits/sec
  "throughput_up_mbps": 25.1, // float: megabits/sec
  "packet_loss_percent": 0.5 // float: 0-100
}
```

---

## Obstruction

```json
{
  "obstruction_percent": 15.0 // float: 0-100
}
```

---

## Environmental

```json
{
  "signal_quality_percent": 85.0, // float: 0-100
  "uptime_seconds": 3600.5, // float
  "temperature_celsius": null // float or null
}
```

---

[Back to API Reference](../README.md) | [Models Index](./README.md)
