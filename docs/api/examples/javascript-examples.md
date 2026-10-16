# JavaScript API examples

Mission Planner uses origin-relative `/api/...` paths through its proxy. A Node
client can prepend its configured backend origin. Check HTTP status explicitly;
`fetch` does not reject on HTTP errors.

```javascript
async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    signal: AbortSignal.timeout(10000),
  });
  const text = await response.text();
  let data = text;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* proxy text */
  }
  if (!response.ok)
    throw new Error(`HTTP ${response.status}: ${JSON.stringify(data)}`);
  return data;
}

const listing = await request("/api/pois/?active_only=false");
listing.pois.forEach((poi) => console.log(poi.id, poi.name));

const etas = await request("/api/pois/etas");
etas.pois.forEach((poi) => console.log(poi.name, poi.eta_seconds));

const poi = await request("/api/pois/", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ name: "Example", latitude: 40.7, longitude: -74.0 }),
});
await request(`/api/pois/${encodeURIComponent(poi.id)}`, { method: "DELETE" });
// Successful DELETE returns null (HTTP 204).
```

See [error handling](../errors-handling.md),
[POI ETA limitations](../poi/eta-endpoints.md) and
[required route query parameters](../eta/waypoint-endpoints.md).
