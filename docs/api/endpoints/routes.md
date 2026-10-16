# Route and geographic endpoints

For KML upload, listing, download, deletion, statistics and route activation,
see the [route management reference](../../route-api-endpoints.md). For mission
lifecycle activation, use the
[Mission V2 contract](./README.md#mission-v2-activation).

## GET `/api/route.geojson`

Returns a GeoJSON `FeatureCollection` containing the selected route and optional
POIs. This is planned route geometry, rather than a recording of position
history. Mission Planner uses native maps; Grafana is not part of the deployed
stack.

| Query parameter    | Default | Meaning                                           |
| ------------------ | ------- | ------------------------------------------------- |
| `route_id`         | omitted | Select this route; otherwise use the active route |
| `include_pois`     | `true`  | Include POI point features                        |
| `include_position` | `false` | Attempt to include current position               |

Coordinates use `[longitude, latitude]` order. A successful request returns HTTP
200, including when the collection has no route feature. Position inclusion is
best effort; unavailable telemetry can omit the position feature.

```bash
curl 'http://localhost:8000/api/route.geojson?include_pois=true' | jq .
```

There is no supported `/geojson` alias or root `/route.geojson` endpoint. For
tabular exports and additional GeoJSON variants, see
[additional endpoints](./additional.md). The exact live schema is available at
`http://localhost:8000/docs`.
