# Configuration API Endpoints

`GET /api/config` returns the current `SimulationConfig`. Both
`POST /api/config` and `PUT /api/config` accept a complete replacement of that
configuration. They are equivalent; neither is a partial merge or PATCH. Omitted
fields take model defaults, which can reset mode and unrelated settings.

Read the full configuration, edit only intended values, and send the full object
back. Configuration replacement resets simulators and cancels the current
simulation run. Use it only when that reset is intended. These runtime changes
do not edit `.env` or the configuration YAML for future service starts.

## Example

Run against an isolated simulation backend. This example reads the complete
object before replacing one field:

```python
import requests

base = "http://localhost:8000"
response = requests.get(f"{base}/api/config", timeout=10)
response.raise_for_status()
config = response.json()
config["route"]["pattern"] = "straight"
response = requests.post(f"{base}/api/config", json=config, timeout=10)
response.raise_for_status()
print(response.json())
```

The configuration includes mode, update interval, route, network, obstruction,
position, dish, and route-following settings. Consult the running `/docs` or
`/openapi.json` for the complete model and validators. Invalid bodies return
422; applying a rejected configuration returns 400; an uninitialized coordinator
returns 503. Successful reads and replacements return 200.

A read/edit/write sequence has no conditional revision guard; coordinate changes
with other operators rather than assuming concurrent edits merge.

## Other Settings

Simulation configuration is separate from persisted operator settings:

- [Overview clocks](overview-clock-settings.md)
- [Manual X-band selection](manual-x-band-selection.md)
- [Overview weather](overview-weather.md)
- [Aviation weather](../aviation-weather.md)
- [Setup configuration](../../setup/configuration.md)

See [API reference](../../api-reference-index.md) for remaining endpoint groups.
