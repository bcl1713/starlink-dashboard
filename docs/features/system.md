# System Configuration & Simulation

## Configuration & Environment

### Environment Variables

All system configuration via `.env` file.

**Core Settings:**

- `STARLINK_MODE` - Operating mode (simulation/live)
- `STARLINK_DISH_HOST` - Terminal IP (live mode)
- `STARLINK_DISH_PORT` - Terminal gRPC port (live mode)
- `PROMETHEUS_RETENTION` - Metrics retention period

**Port Configuration:**

- `STARLINK_LOCATION_PORT` - Backend port (default: 8000)
- `PROMETHEUS_PORT` - Prometheus port (default: 9090)

**See:**
[Environment Variables](../setup/configuration/environment-variables.md)

### Overview settings and diagnostics

The **Configuration** page contains **Overview history window** (5, 15, 30 or 60
minutes, preserving a saved custom duration). The saved window applies to the
aircraft trail and all five network graphs. It does not change the fixed
five-minute rolling-statistics window or polling cadence. Read and save failures
are reported separately; an unsuccessful save can be retried.

**Overview map diagnostics** retains satellite counts, selected planned ID,
status/history availability, ground entry point and configured GEO look angles.
Satellite placement and link geometry are planning analysis, not measured
connectivity. The supported planned-link warning derives from the existing
configured forbidden relative-azimuth rule; it does not establish a connection
or introduce a new alarm. Retained coordinates and geometry can be last known.
Satellite catalog editing remains in Satellite Manager.

### Shared data link visibility

**Configuration → Network Traffic → Network map layers** contains independent
**Starshield data link** and **X-band data link** switches. Both default to
`true`. The **Orbital traffic view** switch restores the optional Starlink
constellation and inferred aircraft-to-PoP path; it defaults to `false`.
**Configuration → Aircraft Traffic → Own aircraft → Aircraft history** shows the
flown track and defaults to `true`. Hiding it also removes the **Track history**
legend entry; history collection, the selected window and network graphs
continue to operate. The switches use `GET /api/overview-links/settings` and
partial `PUT /api/overview-links/settings` updates with strict boolean fields
`starshield_link_enabled`, `x_band_link_enabled`, `orbital_traffic_enabled` and
`aircraft_history_enabled`, plus independent border, marker and panel
preferences. **Overview** contains general panel and mission-layer switches;
**Network Traffic** contains individual network graph switches. The API returns
all 21 confirmed boolean fields; changing one preserves the others, including
concurrent disjoint edits. Orbital visualization requires the Starshield data
link to be enabled and falls back to the direct arc when no usable orbital route
exists. See the [orbital view checks](../testing/orbital-traffic-experiment.md)
for provider, rendering and resource behavior.

Settings persist atomically at `data/settings/overview-links.json`, survive
backend restarts and synchronize mounted Overview windows through five-second
background reads and focus/network recovery refresh. They are installation
settings, not browser storage. Before a confirmed read, controls are disabled
and both links are hidden; the aircraft trail retains its enabled default;
orbital mode also stays off. Read/save failures retain the last confirmed values
and show error feedback; saves do not optimistically change visibility.

Saved settings are compatible with additive schema changes. Missing fields use
their defaults, while existing values (including `false`) remain unchanged.
Unfamiliar saved fields are ignored for this version's display and preserved
during partial saves so another version can read them later. Reads never rewrite
the file. Malformed JSON and invalid recognized values still fail without
replacing the saved data; API updates reject unknown fields.

Starshield visualizes measured aircraft–PoP traffic. X-band activity is a local
illustration; neither switch changes telemetry collection, metric history,
configured selection, warning rules or operational status. See
[Overview data links](overview.md#independent-data-links) for rendering
behavior.

### Configuration API

Runtime configuration management via REST API.

**Endpoints:**

- `GET /api/config` - Get current configuration
- `PUT /api/config` - Update configuration
- `POST /api/config/reload` - Reload from file

**Configurable Settings:**

- Operating mode
- Dish connection details
- Metrics collection intervals
- Feature flags
- Logging levels

**See:** [Configuration Endpoints](../api/endpoints/configuration.md)

---

## REST API

### Interactive API Documentation

Auto-generated API documentation with testing interface.

**URL:** <http://localhost:8000/docs>

**Features:**

- Complete endpoint listing
- Request/response schemas
- Try-it-out functionality
- Authentication testing
- Example payloads
- Error code reference

**Alternative:** ReDoc at <http://localhost:8000/redoc>

### API Categories

**Core Endpoints:**

- Health and status
- System metrics
- Configuration

**Feature Endpoints:**

- POI management
- Route management
- ETA calculations
- Flight status
- Mission planning

**See:** [API Reference Index](../api/README.md)

---

## Simulation Mode Features

### Realistic Telemetry Generation

Generate realistic Starlink metrics without hardware.

**Simulated Data:**

- GPS position (follows routes or circular path)
- Network latency (20-80ms with realistic variance)
- Throughput (100-200 Mbps with patterns)
- Signal quality metrics
- Obstruction simulation
- Speed and heading

**Realism Features:**

- Time-of-day variations
- Weather patterns (optional)
- Realistic noise and jitter
- Connection stability simulation

### Route Following

Simulator automatically follows uploaded KML routes.

**Behavior:**

- Reads waypoint coordinates from KML
- Extracts timing metadata (if present)
- Calculates speeds between waypoints
- Interpolates smooth movement
- Updates position at configured interval

**Configuration:**

- Upload KML via `/api/routes/upload`
- Activate route via `/api/routes/{id}/activate`
- Simulation starts following immediately

## Overview windows and display controls

Leave Overview open on the display and edit Configuration or Missions in another
window. Successful saves refresh clocks, history settings, links, satellites and
active routes every five seconds, plus API response and rendering time. Overview
does not need focus or reload. Mission activation, switching, deactivation and
active-leg edits also refresh generated POIs and departure/arrival timing.
Failed saves never confirm an unsaved draft. Reads retain confirmed data under
the existing error/unavailable UI. Fully suspended browser or OS windows catch
up on resumption; they cannot promise a wall-clock refresh bound.

**Follow aircraft on Overview** is saved in this browser and shared with its
same-origin windows. Manual map exploration pauses following; **Reset map view**
or the remote **Recenter view** restores the configured behavior. Saved settings
preserve the mounted globe and ongoing history. Changing the history window
intentionally changes its displayed range; old bundles are not relabeled as the
new window. REST settings can reach other browsers on the same installation.

In Configuration, **Overview displays** lists labels that match each open
Overview. One display is selected automatically. With multiple displays, choose
the target explicitly. If it closes or stops reporting, controls become
unavailable and require a new selection; they never choose a replacement
silently. **Open Overview** opens a separate window from your click. If no new
display connects, allow popups and check the Overview window.

Display commands require the same origin and browser storage partition. They do
not control another browser, device or profile. **Recenter view** confirms that
the selected display accepted its existing reset action; camera animation may
still be settling. Commands expire after three seconds, and unavailable targets
or rejected actions show feedback. Saved-state refresh continues independently.

**Fullscreen** requests native fullscreen in the selected Overview while keeping
Configuration available. Its **Fullscreen active** / **Windowed** state reflects
actual browser state. Browser policy can reject remote entry; follow the message
**Click Fullscreen in the Overview window to finish.** Click the local Overview
control, then use Escape or its exit control to leave. No permission changes or
special browser flags are required. A timeout cannot cancel a native request
already issued; actual fullscreen changes remain authoritative.

## Shared ADS-B aircraft settings

The optional aircraft layer defaults off. **Military + included** combines the
military feed with saved exact ICAO hexes; **Included only** acquires only those
hexes. Exclusion always wins, including overlap and the own aircraft's hex.
Explicit inclusion permits civilian/unknown classifications and bypasses the
background callsign filter. Callsign substrings match case-insensitively with
OR; an empty filter admits all military traffic. Lists preserve six digits and
zeroes.

Configuration's table contains all global eligible unexpired contacts, including
positions behind Earth or outside Overview's camera. Include/Exclude acts on a
stable hex. Separate saved-list editors retain unavailable/expired entries and
conflicts, and remote polling preserves unrelated unsaved editor text. Controls
wait for backend confirmation; failed saves keep confirmed state and show
errors.

Settings persist across service restart independently of missions. One backend
scheduler acquires every 15 seconds, with bounded individual concurrency and
independent source backoff. Configuration displays source errors and
last-success information. Visible pages poll every five seconds and refresh on
focus; hidden pages catch up on return. Retained observations become Stale at 30
seconds and expire at 120 seconds even through failures or repeated payloads.
Browser receipt never renews a position. Live contacts start empty after backend
restart.

Explicitly included aircraft use one comma-separated provider lookup per shared
acquisition cycle (up to the documented 1,000-code limit, then sequential
chunks). Included batches share backoff and never fall back to individual
requests. See
[provider acquisition](../development/adsb-provider-acquisition.md) for the
verified contract and operator guidance.

Aircraft data: [adsb.lol](https://adsb.lol/),
[ODbL license](https://opendatacommons.org/licenses/odbl/1-0/). Review provider
usage before broad enablement. See the
[API reference](../api/endpoints/overview-adsb.md).
