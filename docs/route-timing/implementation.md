# Route timing implementation guide

## KML format with timing data

Place each UTC timestamp in a named waypoint Placemark's `description`. Keep the
LineString coordinates numeric. Timing is extracted from descriptions and
associated with nearby route points; text appended to a coordinate tuple is not
a timing source.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Route</name>
      <LineString><coordinates>-76.9,38.8,1000 -75.0,38.0,2000</coordinates></LineString>
    </Placemark>
    <Placemark>
      <name>Departure</name>
      <description>Time Over Waypoint: 2035-01-01 16:45:00Z</description>
      <Point><coordinates>-76.9,38.8,1000</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Arrival</name>
      <description>Time Over Waypoint: 2035-01-01 17:15:00Z</description>
      <Point><coordinates>-75.0,38.0,2000</coordinates></Point>
    </Placemark>
  </Document>
</kml>
```

Timestamps require `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`. Seconds are
preserved. Coordinates use longitude, latitude and altitude in meters.

## API usage

For standalone route checks against a backend exposed on port 8000:

```bash
curl -X POST -F 'file=@route.kml' http://localhost:8000/api/routes/upload
curl -X POST http://localhost:8000/api/routes/ROUTE_ID/activate
curl http://localhost:8000/api/routes/active/timing
curl 'http://localhost:8000/api/routes/ROUTE_ID/eta/waypoint/1?current_position_lat=38.8&current_position_lon=-76.9'
curl 'http://localhost:8000/api/routes/live-mode/active-route-eta?current_position_lat=38.8&current_position_lon=-76.9&current_speed_knots=200'
```

Replace `ROUTE_ID` with the upload response identifier. The live-mode endpoint
is a GET query using position and speed parameters; it does not ingest telemetry
with a POST body. For mission operations, activate the owning leg through the
[Mission V2 API](../missions/README.md#mission-v2-activation).

See the [route endpoint reference](../api/endpoints/routes.md) for request
parameters and response fields, and [concepts](concepts.md) for planned versus
live ETA behavior.
