# Phase 2: React Operations Overview Dashboard UI

> **For Hermes:** Start after Phase 1. Use the `test-driven-development` and
> `subagent-driven-development` skills task-by-task; preserve every listed
> commit boundary.

This phase implements deterministic data continuity and the complete responsive
React presentation. The
[master parity contract](../2026-08-29-react-operations-overview.md#parity-contract)
and [Phase 1 contracts](01-contract-and-api.md) remain binding.

## Refresh, continuity, freshness, and persisted preferences

- Dashboard refresh choices: `1s`, `2s`, `5s`, `10s`, `30s`, and paused. Default
  is `1s`; persist under versioned key
  `starlink.operations-overview.preferences.v1`.
- A manual Refresh button invalidates all current/overlay queries and performs
  history reconciliation once, even while paused. Disable duplicate clicks while
  that manual cycle is pending, retain the last valid render, and report
  completion/failure without moving focus.
- Fetch 30-minute history once on entry and on manual refresh. Poll current
  telemetry at the selected interval, append/de-duplicate by server timestamp,
  prune points older than 30 minutes, and reconcile history every 10 seconds. Do
  not download a full 30-minute range every second.
- Poll POIs and active link at selected cadence, route geometry every 5 seconds,
  GEP every 30 seconds, and radar according to the provider frame/cache policy.
  A selected slower cadence is the lower bound for dashboard-owned polls.
- On `document.hidden`, stop scheduled polling and timers that cause network
  traffic; preserve buffers and UI state. On visibility restoration, perform one
  coordinated refresh and resume without burst replay.
- Keep last valid panel/layer data during background fetch and partial failures.
  Never reset map viewport, selected POI categories, layer toggles, expanded
  disclosures, chart visibility, focus, or fullscreen styling on refresh.
- Apply the Phase 1 truthful freshness clock for each source: telemetry/history
  observation, active-link observation, POI generation, route revision, GEP
  observation, and radar frame time. Response generation/client receipt update
  transport last-success only and cannot freshen an older source. Show global
  transport last-success and localized source state. Define stale as
  `age > max(5 seconds, 3 * active refresh seconds)`; paused data is labeled
  `Paused — last updated …`, not stale merely because the operator paused.
- Distinguish initial loading, empty, stale, partial error, total error, and
  recovered. Recovery is announced once in a polite live region; never announce
  each one-second value tick.
- Clocks use a single injectable `now(): Date` source and one shared one-second
  timer. Preferences contain an ordered list of `{label, timeZone}`. UTC is
  immutable, always first, cannot be hidden or deleted, and is restored during
  migration if absent. Other IANA zones may be added, relabeled, reordered, or
  removed after `Intl.DateTimeFormat` validation. Default the four zones above;
  persist locally and test DST boundaries with a fake clock.
- Radar defaults to `true`, can be toggled from the layer disclosure, and is
  persisted. A failed radar layer shows a localized status and toggle/retry;
  vector layers continue.
- Own the six-option POI filter in page preferences with the exact ordered
  label/value contract in the master plan. Default to `departure,arrival`, omit
  the query for All POIs, preserve selection across refresh/recovery, rotation,
  responsive disclosure, remount, and fullscreen, and expose one keyboard/touch
  operable labeled control on desktop and mobile.

## Test-first dashboard tasks and commit boundaries

### Task 7: Implement pure time-series, metric, POI, and IDL utilities

**Files:** `history.ts`, `geometry.ts`, `formatters.ts` and colocated tests.

**Steps:**

1. Write tests for timestamp alignment, de-duplication, chronological ordering,
   30-minute pruning, maximum sample count, five-minute latency min/mean/max,
   upload sign inversion, packet-loss summaries, ETA formatting/sorting,
   exclusion of `already_passed` and `behind`, top-five limit, ETA urgency at
   900/1800/3600 seconds, and all IDL edge cases in the
   [IDL contract](01-contract-and-api.md#international-date-line-handling).
2. Include a fake `now` parameter in every time-dependent utility; no tests may
   wait on wall-clock time.
3. Run focused tests; expected RED.
4. Implement pure functions, rerun; expected PASS.
5. Commit: `feat(frontend): add overview metric and geometry utilities`.

### Task 8: Implement persisted clocks, refresh, and radar preferences

**Files:** preferences, clocks/settings/controls and tests.

**Steps:**

1. With fake timers, test default clocks, 24-hour seconds, DST transitions,
   invalid IANA zone rejection, labels/offsets, immutable first UTC clock,
   preference migration, malformed localStorage fallback, refresh choices,
   default 1 second, paused state, radar default-on/toggle persistence, one
   shared timer, and timer cleanup on unmount. Test all six POI labels/values in
   exact order, default state, All POIs empty/omitted-query encoding,
   persistence migration, and preservation through five scheduled plus manual
   refreshes.
2. Add keyboard/accessibility tests for every control, including POI filter
   selection and its responsive desktop/mobile disclosure; enforce 44×44 CSS px
   touch targets in responsive classes.
3. Run focused tests; expected RED, then implement and expect PASS.
4. Commit: `feat(frontend): add configurable overview controls and clocks`.

### Task 9: Implement continuity-aware data orchestration

**Files:** `useOverviewData.ts` and tests.

**Steps:**

1. Test per-source schedules, bootstrap/reconcile/append behavior, selected
   refresh cadence, manual refresh while paused, duplicate click suppression,
   hidden-tab suspension, visibility catch-up, abort on unmount, localized
   errors, retained last-good data, stale threshold, paused label, recovery
   announcement, and preservation of user state. Independently age telemetry,
   history, POI generation, active-link observation, route revision, cached GEP
   observation, and radar frame clocks; prove response generation/receipt cannot
   hide stale source data and test unknown-time/recovery semantics.
2. Use fake timers and deterministic query mocks. Assert five scheduled
   refreshes plus one manual refresh do not produce an undefined last-good
   snapshot between valid responses.
3. Run focused tests; expected RED, then implement and expect PASS.
4. Commit: `feat(frontend): orchestrate resilient overview refresh`.

### Task 10: Build charts, summaries, gauge, GEP, and POI presentation

**Files:** metric/POI/GEP components and tests; add `uplot` lockfile changes.

**Steps:**

1. Add `uplot` with `npm install uplot` so both package files change together.
2. Test labels, units, thresholds plus text (not color alone), legends,
   current/min/max/mean, upload-negative rendering, null gaps, accessible chart
   summaries/data tables, mobile disclosure, top-five POI card/table parity,
   empty/loading/error/stale states, and retained last-good values.
3. Run focused tests; expected RED, implement components, then expect PASS.
4. Run `npm run lint && npm run build`; expected PASS.
5. Commit: `feat(frontend): render overview metrics and POIs`.

### Task 11: Build the operational map with all layers

**Ownership:** Build the operational map according to the
[Task 11 responsibility map](00-exact-file-map.md#task-11-responsibility-map)
and the
[Task 11 binding contract](00-exact-file-map.md#task-11-binding-contract). Named
paths are advisory ownership examples unless a public import, asset URL, or test
contract explicitly requires one.

**Activation-critical contract:** `OperationalMap` is the public shell and owns
the stable Leaflet tree, `focusCoordinates()` handle, eleven vector groups,
radar `GridLayer`, single timestamp/history identity reconciliation path,
controlled radar retry/preference callbacks from `OverviewPage`, sole
`LayerDisclosure` radar toggle/retry and layer control, internal object-URL
cleanup, same-origin radar CSP boundary, and responsive map interaction behavior
within the continuously mounted Overview/Leaflet tree. `OverviewPage` owns and
persists the radar preference and passes `radarEnabled`, `radarRefreshToken`,
`retryRadar`, `reportRadarResult`, and `onRadarEnabledChange` to
`OperationalMap`. `onRadarEnabledChange` persists the radar preference,
`retryRadar` triggers explicit retry, and `reportRadarResult` uses the
visible-generation token captured when the radar attempt began. Non-radar layer
visibility remains Task 11 mount-local state, with no Task 11 preference-schema
migration. Nginx/browser CSP adds only `blob:` to `img-src` as needed for
internal, revoked radar object URLs, leaves `connect-src` unchanged, adds no
direct RainViewer browser origin or network access, and remains subject to later
exact-head real-browser CSP/network acceptance.

**Steps:**

1. Test exact twelve-layer names/order/default visibility/styles, ArcGIS URL and
   attribution, radar toggle/opacity/zoom, western/eastern IDL segments,
   aircraft heading transform, feature details, fit-to-layers only on first
   valid load or explicit action, scale/measure/zoom controls, textual
   equivalent, and independent layer failure.
2. Test that event-driven lifecycle observation across five scheduled one-second
   refreshes plus one actual manual refresh preserves the Leaflet map instance,
   viewport, selected feature, expanded disclosure, and layer instances within
   the continuously mounted tree. Observers start before the first measured
   request and remain active through manual completion and settle; no
   `fitBounds` occurs in background refresh. Repeated mount/unmount tests prove
   cleanup and fresh defaults, not state persistence across remounts.
3. Run focused tests; expected RED, implement, then expect PASS.
4. Commit: `feat(frontend): add full-parity operational map`.

### Task 12: Compose the responsive page, routing, and accessibility

**Ownership:** Compose the page according to the
[Task 12 responsibility map](00-exact-file-map.md#task-12-responsibility-map)
and the
[Task 12 binding contract](00-exact-file-map.md#task-12-binding-contract). Named
paths are advisory ownership examples unless the routing, exported shell, or CSS
class contracts explicitly require one.

**Activation-critical contract:** Task 12 owns one mounted Overview composition
tree, responsive routing/layout/fullscreen behavior, `.overview-map-region`
height at every accepted viewport, and the 100% fill contract for
`OperationalMap`. It may focus map content only through `focusCoordinates()`,
keeps `LayerDisclosure` inside the map as the sole radar toggle/retry and
layer-control UI, owns controlled radar preference plumbing in `OverviewPage`,
and preserves responsive interaction state across refresh, rotation, responsive
changes, fullscreen, and other rerenders within the continuously mounted tree.
Task 12 must explicitly remove the existing weather-radar checkbox from
`OverviewControls` during composition and must not add a duplicate. It leaves
browser acceptance to Tasks 13-14.

**Steps:**

1. Test `/` redirects with replacement to `/overview`, Overview appears first in
   navigation, brand links to `/overview`, `aria-current` is present, all old
   routes still resolve, and browser Back behavior is preserved.
2. Test one `main`, skip link, logical headings, visible focus, reduced motion,
   polite status live region, and no one-second live spam. For fullscreen,
   assert screenshots and overflow/layout before entry, during native
   fullscreen, during kiosk fallback after rejected/unsupported API, and after
   exit; prove controls/filter/layers/map viewport survive and triggering focus
   is restored.
3. Implement desktop grid and responsive stacking/disclosure from
   [Responsive acceptance details](#responsive-acceptance-details). Fullscreen
   API invocation must occur only from a user gesture; exiting must retain
   dashboard state.
4. Run component suite, lint, and build; expected PASS.
5. Commit: `feat(frontend): add operations overview landing page`.

## Responsive acceptance details

### 1920×1080

- Four clocks visible together; map is largest region; POI/latency/throughput
  rail remains legible; GEP/obstruction/packet-loss strip visible.
- Primary operations fit one viewport; only clearly secondary details may
  require scrolling.
- Planning navigation is present but subordinate; fullscreen is keyboard
  operable and state-preserving.

### 1280×800 and 1024×768

- No page overflow. Clocks wrap deliberately. Map precedes detail and remains at
  least 320 px high. Summary values remain adjacent to or directly after it.
- Cards/charts become full width as needed; a wide table may scroll only inside
  an explicitly labeled region.

### 768×1024

- Compact navigation and clocks remain reachable. Controls are at least 44×44.
- Map, summaries, POIs, and charts stack in that priority; disclosures are
  obvious and dismissible.

### 390×844 and 320×568

- Initial viewport communicates connection/freshness, current route/position
  state, UTC, and highest-priority network state.
- Clock list keeps UTC directly visible; other clocks are fully available via a
  labeled disclosure.
- Map supports normal page scrolling until explicit map interaction is enabled.
- POI cards retain ETA, name, category/type, and urgency.
- Charts may initially show textual current/min/average/max summaries, but a
  keyboard/touch disclosure exposes the full chart and accessible data table.
- The complete layer list, radar control, filters, feature details, retry,
  refresh, and settings remain available. Rotation preserves all state.
