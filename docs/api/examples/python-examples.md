# Python API examples

These examples require `requests` and an accessible backend. Use resource IDs
returned by the server. See [error handling](../errors-handling.md).

```python
import requests

base = "http://localhost:8000"

def request(method, path, **kwargs):
    response = requests.request(method, base + path, timeout=10, **kwargs)
    response.raise_for_status()
    return None if response.status_code == 204 else response.json()

listing = request("GET", "/api/pois/", params={"active_only": False})
print("Total:", listing["total"])
for poi in listing["pois"]:
    print(poi["id"], poi["name"])

poi = request("POST", "/api/pois/", json={
    "name": "Example POI", "latitude": 40.7, "longitude": -74.0,
})
request("PUT", f"/api/pois/{poi['id']}", json={"name": "Updated example"})
request("DELETE", f"/api/pois/{poi['id']}")  # 204: no JSON body

etas = request("GET", "/api/pois/etas")
for poi in etas["pois"]:
    print(poi["name"], poi["eta_seconds"], poi["distance_meters"])
```

ETA position-query precedence has limitations; see
[POI ETA](../poi/eta-endpoints.md#calculation-method). For route calculations,
provide required coordinates shown in
[waypoint ETA](../eta/waypoint-endpoints.md) and
[progress](../eta/progress-endpoints.md). Configuration updates follow the
[configuration contract](../endpoints/configuration.md); POST replaces a
complete configuration rather than applying a partial patch.
