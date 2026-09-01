# React Operations Overview

The React **Operations Overview** is the default Mission Planner landing page.
Use this guide for operating the overview, understanding its data and status,
and moving safely between it and Grafana during the transition.

**Related:** [Quick Start](./setup/quick-start.md) |
[Monitoring API reference](./api/monitoring.md) |
[Grafana transition](#grafana-transition-and-retirement) |
[Troubleshooting](#troubleshooting-and-escalation)

## Access and scope

Open the Mission Planner at `<http://localhost:5173/overview>` in local frontend
development, or use the deployed Mission Planner origin followed by `/overview`.
The `/` route redirects to `/overview`. Use the application navigation for
missions, satellites, POIs, routes, export, and configuration; direct links to
those routes remain available.

The page combines an operational map, world clocks, telemetry, monitoring
history, POI quick reference, and ground-entry-point information. It is an
operational view, not a substitute for source validation or incident procedure:

- Simulation mode generates representative telemetry and must not be treated as
  hardware observation.
- Each panel reports its own source timestamp. A response-generation or browser
  receipt time does not make an old source observation fresh.
- Empty, unavailable, stale, or failed panels do not establish that a system is
  healthy. Confirm the source and use the escalation signals below.
- The overview does not expose a Prometheus query interface, Grafana session,
  datasource proxy, or a ground-entry-point public IP.

## Daily operation

### Read the status before the number

Panels intentionally make source condition visible alongside any retained data:

| Displayed state       | Meaning                                                        | Operator action                                                                                                |
| --------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Loading               | The first source request is in progress.                       | Wait for completion; do not infer zero or healthy data.                                                        |
| Refreshing            | A new request is in progress while prior data remains visible. | Use the retained value with its source timestamp.                                                              |
| Ready                 | The panel has usable data.                                     | Check its source timestamp and operational context.                                                            |
| Paused                | The configured scheduled refresh is paused.                    | Resume a cadence or use **Refresh overview**.                                                                  |
| Stale                 | The last source observation is outside its freshness policy.   | Retry, then investigate the source before acting on it.                                                        |
| Unavailable           | The source has no currently available value.                   | Check the applicable API/service and logs.                                                                     |
| Source refresh failed | A request failed.                                              | Select the panel's **Retry** control or refresh the overview; preserve the error and timestamp for escalation. |

A panel can retain last-good content during refresh or failure. That is
deliberate continuity behavior, not proof that the retained content is current.
If a source timestamp is absent, the UI labels it as unavailable rather than
inventing a freshness time.

### Controls and preferences

Select **Overview controls** to reveal the controls. They reflow into the
responsive layout rather than disappearing on narrow screens.

- Choose a refresh cadence of 1, 2, 5, 10, or 30 seconds, or **Paused**.
- History follows the selected cadence but is never requested more often than
  every 5 seconds (12 requests per minute). A pending history request is shared;
  it does not delay current status or other overview sources.
- Select a POI category, then use **Refresh overview** for an immediate refresh.
  The button remains the focus target while its request is pending.
- Add, label, move, or remove world clocks in the clock settings. UTC (Zulu)
  remains present.
- Enable or disable the radar layer from the map controls. The preference,
  refresh cadence, POI filter, clocks, and disclosure state are stored locally
  in the browser under the versioned overview-preferences key. They are not a
  shared operator profile and may be unavailable in privacy-restricted storage.

The map and the rest of the page remain useful when radar is disabled or its
provider cannot be reached. A radar failure is not telemetry failure.

### Fullscreen and accessibility

Use **Enter fullscreen** for a focused display. When the browser permits the
native Fullscreen API, the overview enters native fullscreen. If it is absent,
rejected, or errors, the page explicitly reports **Fullscreen unavailable —
using kiosk view** and uses the in-page kiosk layout instead. Use **Exit
fullscreen** or **Exit kiosk view** to leave; `Escape` also exits kiosk view.
Focus returns to the trigger after exit and the inline scroll position is
restored.

All controls have named, keyboard-operable HTML controls and visible
focus-visible treatment. The page publishes important status changes through a
polite live region. Map motion requested by a map action is reduced-motion
aware; operators who prefer reduced motion should retain that browser/OS
preference.

The implementation includes automated axe coverage with no serious or critical
violations permitted by the acceptance plan, plus manual keyboard,
screen-reader, 44-by-44 target, reduced-motion, and WCAG 2.2 AA contrast
evidence requirements. Those checks are release/rollout evidence, not a blanket
claim about an arbitrary deployment. At this documentation revision, the PR's
documented public check is its lint/format check; review the exact-head browser
and real-runtime evidence before declaring browser or contrast acceptance
complete.

## Monitoring and API boundary

The browser uses origin-relative `/api/...` requests through the Mission Planner
origin. Nginx forwards those requests to the backend; the browser is not given a
Prometheus URL, Grafana URL, container hostname, upstream credential, or
arbitrary query capability.

### Overview sources

The UI consumes typed responses for current status, fixed monitoring history,
POI ETAs, route coordinates, active X-link state, cached ground-entry-point
state, and radar tiles. Source times remain distinct: current telemetry uses its
observation timestamp, history samples use Prometheus observation timestamps,
route coordinates use a route revision time, and radar uses its provider frame
time when available. Ground-entry-point and other responses distinguish an
observed time from response generation time where supplied.

The overview-specific API surface is intentionally narrow:

| Endpoint                                            | Contract used by the overview                                                                                                                                                                                                                         |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/monitoring/history`                       | Returns a server-selected UTC window of six fixed series: latitude, longitude, latency, downlink throughput, uplink throughput, and packet loss. `range_seconds` defaults to 1800 and accepts 60–3600; `step_seconds` defaults to 1 and accepts 1–60. |
| `GET /api/monitoring/ground-entry-point`            | Returns cached ground-entry-point display/location state. It returns HTTP 200 with `available: false` and null details when no cached value exists, and does not trigger discovery on request.                                                        |
| `GET /api/weather/radar/rainviewer/{z}/{x}/{y}.png` | Returns a validated same-origin radar tile for a valid XYZ coordinate. It is a tile delivery route, not a general-purpose external fetch proxy.                                                                                                       |

History always contains the fixed series order, including empty sample lists.
Finite metric values are numbers; unavailable/non-finite samples are represented
as `null`. A successful history response includes `generated_at`,
`window_start`, `window_end`, `range_seconds`, `step_seconds`, and `series`;
each series has a metric name and timestamp/value samples. Do not build against
Grafana's internal queries or duplicate datasource plumbing as if it were this
API contract.

For history, safe error codes are exposed as follows: `429`
`monitoring_rate_limited` (with `Retry-After`), `503`
`monitoring_capacity_unavailable`, `502` `monitoring_upstream_error`, and `504`
`monitoring_upstream_timeout`. Treat them as source/service signals; they do not
reveal the internal Prometheus URL or upstream body.

### Privacy and CSP boundary

Radar metadata and provider tile retrieval occur server-side. The browser loads
the resulting tile through the same-origin API route; it does not contact
RainViewer directly. The delivered Mission Planner CSP allows same-origin image
content, `data:`, `blob:`, OpenStreetMap tiles, and the documented ArcGIS image
origin. Its `connect-src` remains same-origin plus WebSocket allowances; it does
not add Prometheus, Grafana, or RainViewer as a browser connection origin.

This boundary limits direct-browser exposure but does not make third-party map
or radar data authoritative. Do not place private URLs, credentials, Prometheus
queries, or a ground-entry-point IP in browser configuration, support captures,
or escalation notes.

## Troubleshooting and escalation

Start with the panel state and source timestamp, then make a bounded request. Do
not change an endpoint, CSP policy, or service configuration simply to remove a
UI warning.

| Symptom                                      | Verify                                                                                | Immediate response                                                                                  | Escalate with                                                                                                   |
| -------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Several panels are unavailable or stale      | `curl http://localhost:8000/health` and `curl http://localhost:8000/api/status`       | Use panel retry/manual refresh; check backend logs.                                                 | Page URL, UTC observation/source timestamps, affected panels, HTTP status/error code, and backend log interval. |
| History is failing, throttled, or timing out | `curl 'http://localhost:8000/api/monitoring/history?range_seconds=60&step_seconds=1'` | Reduce repeated manual refreshes; preserve `429`, `502`, `503`, or `504` details.                   | Response status/safe code, `Retry-After` if present, request time, and Prometheus/backend health.               |
| Ground entry point is unavailable            | `curl http://localhost:8000/api/monitoring/ground-entry-point`                        | Treat `available: false` as unavailable cached data, not a lookup failure to bypass in the browser. | Response `available`, observed/generated times, and backend discovery/cache logs.                               |
| Radar is absent or stale                     | Disable radar to preserve vector operations; retry the layer later.                   | Check the same-origin tile request and Nginx/backend logs; do not add the provider to browser CSP.  | Tile path, HTTP status, frame timestamp if present, CSP console message, and time range.                        |
| Fullscreen falls back to kiosk               | Confirm the visible fallback message and test exit.                                   | Operate in kiosk view; use the exit button or `Escape`.                                             | Browser/version, native fullscreen failure behavior, keyboard result, and whether focus returned.               |

See [backend troubleshooting](./troubleshooting/services/backend.md) for backend
and live-mode diagnostics. Keep Grafana available as the fallback during the
transition; see the next section rather than treating a React panel failure as
authorization to retire it.

## Grafana transition and retirement

### Current dual-run relationship

`/overview` is the canonical landing and day-to-day React operations path.
Grafana at `<http://localhost:3000>` remains deployed during dual-run as the
documented operational fallback and continues to host its existing dashboards,
including its broader dashboard-specific views. The React overview does not
depend on a Grafana endpoint, session, datasource proxy, plugin, dashboard, port
3000, or asset to function.

Use `/overview` for the React operations overview and Grafana for dashboards or
functions that have not been explicitly verified as equivalent in React. Do not
infer that every Grafana dashboard, time range, annotation, threshold, or export
function has a React replacement merely because `/overview` is the default.

### Rollback and verification

For an operational interruption, navigate to Grafana while it remains available.
For a code rollback, revert the overview change on `dev` and rebuild the backend
and Mission Planner according to the deployment procedure. Verify backend
health, old management routes, Grafana availability, and that no deployed
frontend still calls a removed `/api/monitoring/*` endpoint. Do not remove
Prometheus or Grafana volumes or remove new endpoints independently of a
frontend that still consumes them.

Before promoting beyond dual-run, verify `/` redirects to `/overview`, direct
links to existing management routes still work, the same-origin API/CSP/tile
behavior works through the deployed Nginx, and side-by-side parity is accepted
for the applicable operational window. Observe API latency/error rate,
Prometheus query load, browser memory/network, stale frequency, tile failures,
and operator feedback during a bounded soak.

### No approved retirement yet

Grafana retirement has **no approved date or owner in this change**. It is an
explicitly unapproved, separately scoped follow-up—not preparation work for this
PR. A retirement decision requires documented and approved parity for every
retained control and accessible alternative; deterministic and responsive
acceptance; no-Grafana static/runtime/browser-network proof; representative soak
and recovery evidence; operator sign-off and rollback drill; documentation and
bookmark audit; and an explicit decision on whether the scope is only Fullscreen
Overview or all remaining Grafana dashboards. Prometheus remains after any
future Grafana decision.

Until that gate is approved and its separate change merges, Grafana is live and
is the rollback/fallback path. Details of its current dashboards remain in the
[Grafana Dashboards Reference](./grafana-dashboards.md).
