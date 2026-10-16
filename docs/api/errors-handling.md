# Client error handling and troubleshooting

Use bounded request timeouts, check status before parsing successful payloads,
and accept string, array or object error details. No common `error_code` is
promised. DELETE success may have no body.

```python
import requests

response = requests.get("http://localhost:8000/api/pois/", timeout=10)
if not response.ok:
    try:
        error = response.json()
    except ValueError:
        error = response.text
    raise RuntimeError(f"HTTP {response.status_code}: {error}")
for poi in response.json()["pois"]:
    print(poi["id"], poi["name"])
```

```javascript
// Mission Planner proxies /api on the same origin.
async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    signal: AbortSignal.timeout(10000),
  });
  const text = await response.text();
  let body = text;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* proxy text */
  }
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${JSON.stringify(body)}`);
  }
  return body; // null for HTTP 204
}
```

Retry read requests only for transient failures with bounded backoff; respect
`Retry-After` when supplied. Do not automatically replay creation, import,
activation or deletion after an ambiguous transport failure: first inspect the
persisted state. Fix 400/422 requests and resolve 409 lifecycle conflicts.

For persistent failures, inspect `/health`, the exact response and service logs:

```bash
curl -i http://localhost:8000/health
./scripts/compose.sh logs --tail=100 starlink-location
```

HTTP 200 health can still report `degraded`; check its body. Verify IDs through
`.pois` and `.routes` in their list envelopes. Inspect configured storage paths
and permissions if persistence fails; preserve a backup before repairing data.
Do not reset a POI file as a generic response to HTTP 500.

See [troubleshooting](../troubleshooting/README.md) and
[error scenarios](errors-scenarios.md).
