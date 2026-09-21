# Overview Clock Settings API

[Back to API endpoints](./README.md) | [Configuration endpoints](./configuration.md)

## Persisted Four-Clock Configuration

The Overview dashboard has one persistent, four-clock configuration. Each clock
has a non-empty `label` and an IANA `time_zone`. The service uses these defaults
when no saved configuration is available:

1. `Zulu / UTC` (`UTC`)
2. `Washington, DC` (`America/New_York`)
3. `Omaha, NE` (`America/Chicago`)
4. `Tokyo, JP` (`Asia/Tokyo`)

## GET `/api/overview-clocks/settings`

Retrieve the complete persistent clock collection.

**Response:**

```json
{
  "clocks": [
    {"label": "Zulu / UTC", "time_zone": "UTC"},
    {"label": "Washington, DC", "time_zone": "America/New_York"},
    {"label": "Omaha, NE", "time_zone": "America/Chicago"},
    {"label": "Tokyo, JP", "time_zone": "Asia/Tokyo"}
  ]
}
```

**Status Codes:**

- `200 OK` — settings returned
- `503 Service Unavailable` — clock settings store is not initialized

## PUT `/api/overview-clocks/settings`

Replace the complete persistent collection. The request must contain exactly four
clock mappings. Each `label` must be non-blank, and every `time_zone` must be a
valid IANA timezone.

**Request Body:**

```json
{
  "clocks": [
    {"label": "Zulu / UTC", "time_zone": "UTC"},
    {"label": "Washington, DC", "time_zone": "America/New_York"},
    {"label": "Omaha, NE", "time_zone": "America/Chicago"},
    {"label": "Tokyo, JP", "time_zone": "Asia/Tokyo"}
  ]
}
```

**Response:** `200 OK` with the persisted collection.

**Status Codes:**

- `422 Unprocessable Entity` — the collection does not contain exactly four
  clocks, a label is blank, or a timezone is invalid
- `503 Service Unavailable` — clock settings store is not initialized

## Mission V2 Clock Lifecycle

Activating a Mission V2 leg preserves operator-edited clocks 1 and 2. It updates
only clocks 3 and 4 from the active route's first and last endpoint locations,
respectively. If either endpoint location cannot be resolved, that slot falls
back to Omaha (`America/Chicago`) or Tokyo (`Asia/Tokyo`).

Deactivating Mission V2 legs also preserves clocks 1 and 2 and restores only
clocks 3 and 4 to the Omaha and Tokyo defaults. The unchanged first two clocks
remain persistent operator settings across these lifecycle events.
