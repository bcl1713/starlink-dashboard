# ETA Metrics & Cache Endpoints

[Back to API Reference](../README.md) | [ETA Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## GET `/api/routes/metrics/eta-cache`

Get ETA caching performance metrics.

**Description:** Returns statistics about the ETA cache system, useful for
performance monitoring.

**Response:**

```json
{
  "cache_enabled": true,
  "ttl_seconds": 5,
  "total_cache_hits": 1250,
  "total_cache_misses": 342,
  "hit_rate_percent": 78.5,
  "cached_entries": 23,
  "average_calculation_time_ms": 12.5,
  "last_cleanup": "2025-11-04T10:30:00Z"
}
```

**Status Codes:**

- `200 OK` - Cache metrics retrieved

**Use Case:** Performance monitoring, cache optimization, system diagnostics.

---

## GET `/api/routes/metrics/eta-accuracy`

Get historical ETA accuracy statistics.

**Description:** Returns how accurate the ETA predictions have been, comparing
predicted vs actual arrivals.

**Response:**

```json
{
  "total_predictions": 150,
  "total_arrivals": 127,
  "accuracy_stats": {
    "average_error_seconds": 45.3,
    "min_error_seconds": -120,
    "max_error_seconds": 240,
    "median_error_seconds": 30.0,
    "std_deviation_seconds": 67.5
  },
  "recent_predictions": [
    {
      "predicted_time": "2025-11-04T10:30:00Z",
      "actual_arrival_time": "2025-11-04T10:31:30Z",
      "error_seconds": 90,
      "destination": "waypoint_5"
    }
  ]
}
```

**Status Codes:**

- `200 OK` - Accuracy metrics retrieved

**Use Case:** ETA algorithm validation, accuracy tracking, continuous
improvement.

---

## POST `/api/routes/cache/cleanup`

Clean up expired cache entries.

**Description:** Removes TTL-expired entries from the ETA cache.

**Response:**

```json
{
  "cleaned_entries": 12,
  "remaining_entries": 23,
  "timestamp": "2025-11-04T10:30:00Z"
}
```

**Status Codes:**

- `200 OK` - Cache cleaned

**Use Case:** Maintenance, memory management, periodic cleanup.

---

## POST `/api/routes/cache/clear`

Clear all ETA cache entries.

**Description:** Removes all entries from the ETA cache immediately.

**Response:**

```json
{
  "message": "Cache cleared",
  "cleared_entries": 35,
  "timestamp": "2025-11-04T10:30:00Z"
}
```

**Status Codes:**

- `200 OK` - Cache cleared

**Use Case:** Cache reset, troubleshooting, system maintenance.

---

## Examples

### cURL Examples

**Get Cache Metrics:**

```bash
curl http://localhost:8000/api/routes/metrics/eta-cache | jq .
```

**Clear Cache:**

```bash
curl -X POST http://localhost:8000/api/routes/cache/clear
```

### Python Examples

```python
import requests

# Get cache metrics
response = requests.get('http://localhost:8000/api/routes/metrics/eta-cache')
metrics = response.json()
print(f"Cache hit rate: {metrics['hit_rate_percent']}%")

# Clear cache
response = requests.post('http://localhost:8000/api/routes/cache/clear')
result = response.json()
print(f"Cleared {result['cleared_entries']} entries")
```

---

[Back to API Reference](../README.md) | [ETA Index](./README.md)
