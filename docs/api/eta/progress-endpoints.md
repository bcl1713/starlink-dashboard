# Route progress and timing

## GET `/api/routes/{route_id}/progress`

Requires numeric query parameters `current_position_lat` and
`current_position_lon`; this endpoint does not infer them from telemetry.

```bash
curl 'http://localhost:8000/api/routes/ROUTE_ID/progress?current_position_lat=40.7&current_position_lon=-74.0' | jq .
```

The response contains `current_waypoint_index`, `current_waypoint_name`,
`progress_percent`, `total_route_distance_meters`, `distance_completed_meters`,
`distance_remaining_meters`, `expected_total_duration_seconds`,
`expected_duration_remaining_seconds` and `average_speed_knots`. Handle nullable
or unavailable timing values rather than assuming a destination ETA is present.

Missing route returns 404; invalid/missing query arguments return 422; missing
manager or calculation failures return 500.

## GET `/api/routes/active/timing`

Returns a flat timing dictionary, not a nested `timing_profile` or segment list.
Available fields include `route_name`, `has_timing_data`, planned and actual
`departure_time`/`arrival_time`, `flight_status`, `is_departed`, `is_in_flight`,
`total_expected_duration_seconds` and `segment_count_with_timing`.

No active route returns HTTP 200 with
`{"has_timing_data":false,"message":"No active route"}`. An active route without
a profile returns the same flag with `"Active route has no timing data"`. A
missing route manager returns 500.

Source: `app/api/routes/eta.py`, `app/api/routes/timing.py` and
`app/services/route_eta/calculator.py`. See [ETA index](README.md).
