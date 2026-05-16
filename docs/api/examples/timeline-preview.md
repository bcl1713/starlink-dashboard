# Timeline Preview API Examples

**Purpose**: Practical examples for the real-time mission leg timeline preview endpoint.
**Audience**: API consumers, integrators, frontend developers

[Back to API examples](./README.md) | [Back to API reference](../README.md)

---

## cURL Example

```bash
curl -X POST \
  "http://localhost:8000/api/v2/missions/mission-001/legs/leg-001/timeline/preview" \
  -H "Content-Type: application/json" \
  -d '{
    "transports": {
      "initial_x_satellite_id": "X-1",
      "initial_ka_satellite_ids": ["AOR", "POR"],
      "x_transitions": [
        {
          "id": "x-transition-1",
          "latitude": 35.0,
          "longitude": -120.0,
          "target_satellite_id": "X-2"
        }
      ],
      "ka_outages": [
        {
          "start_time": "2025-10-27T17:00:00Z",
          "duration_seconds": 600
        }
      ],
      "aar_windows": [
        {
          "id": "aar-1",
          "start_waypoint_name": "WP12",
          "end_waypoint_name": "WP16"
        }
      ],
      "ku_overrides": []
    },
    "adjusted_departure_time": "2025-10-27T17:25:00Z"
  }' | jq .
```

## Python Example

```python
import requests

payload = {
    "transports": {
        "initial_x_satellite_id": "X-1",
        "initial_ka_satellite_ids": ["AOR", "POR"],
        "x_transitions": [
            {
                "id": "x-transition-1",
                "latitude": 35.0,
                "longitude": -120.0,
                "target_satellite_id": "X-2",
            }
        ],
        "ka_outages": [
            {
                "start_time": "2025-10-27T17:00:00Z",
                "duration_seconds": 600,
            }
        ],
        "aar_windows": [
            {
                "id": "aar-1",
                "start_waypoint_name": "WP12",
                "end_waypoint_name": "WP16",
            }
        ],
        "ku_overrides": [],
    },
    "adjusted_departure_time": "2025-10-27T17:25:00Z",
}

response = requests.post(
    "http://localhost:8000/api/v2/missions/mission-001/legs/leg-001/timeline/preview",
    json=payload,
    timeout=30,
)
response.raise_for_status()
preview = response.json()

print(preview["mission_leg_id"])
print(preview["statistics"]["degraded_seconds"])
```

## JavaScript Example

```javascript
const response = await fetch(
  'http://localhost:8000/api/v2/missions/mission-001/legs/leg-001/timeline/preview',
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      transports: {
        initial_x_satellite_id: 'X-1',
        initial_ka_satellite_ids: ['AOR', 'POR'],
        x_transitions: [
          {
            id: 'x-transition-1',
            latitude: 35.0,
            longitude: -120.0,
            target_satellite_id: 'X-2',
          },
        ],
        ka_outages: [
          {
            start_time: '2025-10-27T17:00:00Z',
            duration_seconds: 600,
          },
        ],
        aar_windows: [
          {
            id: 'aar-1',
            start_waypoint_name: 'WP12',
            end_waypoint_name: 'WP16',
          },
        ],
        ku_overrides: [],
      },
      adjusted_departure_time: '2025-10-27T17:25:00Z',
    }),
  }
);

if (!response.ok) {
  throw new Error(`Preview request failed: ${response.status}`);
}

const preview = await response.json();
console.log(preview.statistics);
```

---

## Usage Notes

- Preview requests are ephemeral; they do not persist the timeline.
- Use the same payload shape the frontend sends when you want parity with the UI.
- If the request returns `400`, check the adjusted departure time and transport configuration first.
- The returned `samples[]` array is what powers the preview map overlay, while
  `segments[]` drives the table and status badges.
- If you are testing a long route, expect the response to stay the same shape
  even though the UI renders the table lazily.

---

## Related Documentation

- [Timeline Preview Models](../models/timeline-preview.md)
- [Timeline Preview Endpoint](../endpoints/timeline-preview.md)
- [Mission Planning Guide](../../missions/planning/overview.md)
