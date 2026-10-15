# Active-route ETA

## GET `/api/routes/live-mode/active-route-eta`

This is a GET with required numeric query parameters `current_position_lat` and
`current_position_lon`. Optional `current_speed_knots` defaults to 500.0. There
is no POST JSON position-update contract.

```bash
curl 'http://localhost:8000/api/routes/live-mode/active-route-eta?current_position_lat=40.7&current_position_lon=-74.0' | jq .
```

An active route returns `has_active_route: true`, `route_name`,
`current_position` (latitude, longitude, speed_knots), `progress`,
`timing_profile` and nullable `next_waypoint_eta`. `progress` uses the
[route progress fields](progress-endpoints.md). The supplied speed is echoed in
`current_position`; this handler does not pass it into the waypoint calculation.

No active route returns HTTP 200 with
`{"has_active_route":false,"message":"No active route"}`. Missing/invalid query
arguments return 422; missing route manager or calculation failures return 500.

Source: `app/api/routes/eta.py`. See [ETA index](README.md).
