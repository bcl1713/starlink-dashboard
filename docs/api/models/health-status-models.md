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
    "throughput_down_mbps": null,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "metric_availability": {
    "latency_ms": true,
    "throughput_down_mbps": false,
    "throughput_up_mbps": true,
    "packet_loss_percent": true,
    "obstruction_percent": true
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 3600.5,
    "temperature_celsius": null
  },
  "ground_entry_point": null
}
```

The four `network` values and `obstruction.obstruction_percent` are
`number | null`: `null` means unavailable; a measured zero remains `0` with its
availability flag `true`. `metric_availability` always contains five boolean
flags, independently set for each source reading. Missing provenance defaults
to five `false` flags, not inferred observations from internal numeric values.
The example above shows partial loss of downlink, with valid zero packet loss.
Position, environmental fields (including signal quality), and units are
unchanged by this contract.

`timestamp` is the original acquisition time of the batch, **not request time**.
A failed whole-batch collection does not renew it; cached telemetry may therefore
be old. A fresh batch can still have unavailable individual metrics. Consumers
must check both collection age and per-metric availability; availability alone
does not establish freshness. An old response without `metric_availability`
must be treated as unverified for all five metrics, even if its values are zero
or its timestamp looks fresh.

---

## MetricAvailability and live source mapping

| Availability flag / output field | Live source                      | Conversion             |
| -------------------------------- | -------------------------------- | ---------------------- |
| `latency_ms`                     | `status.pop_ping_latency_ms`     | milliseconds unchanged |
| `throughput_down_mbps`           | `status.downlink_throughput_bps` | divide by `1e6`        |
| `throughput_up_mbps`             | `status.uplink_throughput_bps`   | divide by `1e6`        |
| `packet_loss_percent`            | `status.pop_ping_drop_rate`      | multiply by `100`      |
| `obstruction_percent`            | `status.fraction_obstructed`     | multiply by `100`      |

Only when the primary obstruction key is **absent**, use
`obstruction.fraction_obstructed` with the same conversion. An explicitly null
or invalid primary value does not trigger fallback. Integer/float source values
must be finite, including after conversion; zero is valid. Missing keys, null,
booleans, strings, and non-finite values are unavailable. Internal numeric
compatibility placeholders remain implementation details, not status readings.
Simulation explicitly marks its generated five readings available.

Verified against installed `starlink-grpc-core` 1.2.5: `status_data()` returns
`(status, obstruction, alerts)` and supplies the five readings in `status`.
No separate field-validity flag governs these readings in that response.
`obstruction.valid_s` is documented by the library as having unclear semantics,
apparently describing completeness of obstruction-location detail. It is not a
documented boolean validity veto on `status.fraction_obstructed`; a null
`valid_s` does not suppress a finite status fraction. GPS readiness and SNR
metadata do not govern these five readings.

This nullable/provenance projection applies to `/api/status` only. The existing
Prometheus updater and `/metrics` export do not yet honor the new
flags; they can still publish internal compatibility zeros. Do not use those
exports as verified current observations until the separate exporter work is
complete. Older retained history cannot be retrospectively verified by this
contract.

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

All four fields are `number | null` in `/api/status`, gated by their matching
`metric_availability` flags. Units remain milliseconds, Mbps, and percent.

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

`obstruction_percent` is `number | null` in `/api/status`, gated by
`metric_availability.obstruction_percent`.

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
