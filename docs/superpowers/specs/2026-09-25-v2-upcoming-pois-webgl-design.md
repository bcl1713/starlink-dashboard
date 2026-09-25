# V2 Upcoming POIs and WebGL Acceptance Recovery — Design

## Purpose

Restore trustworthy V2 Overview acceptance by separating route-relative POI visibility from stale calendar timestamps and by certifying WebGL2 in the platform-owned headed browser profile.

The intended user-facing rule is: generated Upcoming POIs reflect their position along the active route, not whether a static KML schedule happens to predate the wall clock.

## Evidence and scope

The exact-head non-final diagnostic at `e657d66d083b104617d7463d780746214a54ae14` established:

- The visible create → KML upload → add leg → activate → Overview flow completed and activation returned 200.
- The active route name was present in the Globe legend.
- `/api/overview/upcoming-pois` returned 200 with generated POIs but state `no_upcoming_pois`; the frontend correctly filtered its rows and rendered the empty state.
- The tracked fixture’s route window was 2025-01-01 while capture occurred in 2026; backend projection set `eta_seconds = -1` and excluded the POIs under the existing wall-clock eligibility rule.
- The pinned headed Chromium under Xvfb cannot create WebGL2 without flags, but passed three independent exact-viewport probes with `--use-gl=angle --use-angle=swiftshader`.
- Prometheus was intentionally absent from the reduced topology and explains the separate Overview-history 503; it is not causal for Upcoming POI projection.

This delivery changes only V2 POI projection semantics and the externally administered acceptance-browser launch profile. It does not add Prometheus to the two-service acceptance topology, weaken final evidence requirements, change user-visible journey steps, or enable Chromium’s unsafe SwiftShader opt-in.

## Product semantics: route-relative Upcoming POIs and ETA clock domain

### Rule

For an active route, eligibility is route-relative, while ETA remains mode-appropriate and truthful:

- **In flight (live or simulation):** a generated POI is upcoming exactly when its projected route progress is at or ahead of current route progress. Its ETA is estimated strictly from the current position/progress and the estimated time to reach that POI from now. Historical scheduled timestamps do not determine either visibility or estimated ETA after departure.
- **Pre-departure, before the expected departure:** anticipated ETA is clock-based from the tracked expected waypoint/departure schedule. Generated route POIs remain upcoming in route order.
- **Pre-departure, after the expected departure:** treat the expected departure as now for anticipated ETA calculation. Preserve each POI's planned elapsed route duration from departure, but shift the clock baseline to now; do not return historical negative/`-1` ETA simply because the planned departure is in the past. Generated route POIs remain upcoming in route order.
- **Post-arrival:** no POI is upcoming.
- POIs lacking valid kind/coordinates remain excluded as today.

Simulation follows the same state rules. Simulations normally transition promptly to in-flight, so their ETA naturally becomes the current-position estimate; no simulation-only calendar exception is needed.

`estimated_arrival_time`, `eta_seconds`, ETA type, sorting, and map-retention remain independently truthful. The table eligibility rule must not silently rewrite ETA values or represent a shifted anticipated ETA as telemetry.

### Backend boundary

The ETA projection layer owns calculation of anticipated/estimated ETA. It must add an explicit overdue-predeparture branch that derives a POI's planned duration from the route's expected departure and expected waypoint time, then anchors that duration at calculation time when expected departure has passed. In-flight calculation continues to use live route position/progress and speed.

`project_overview_upcoming_pois(...)` owns `upcoming` and response state. It must derive the eligibility boolean from flight phase and route progress, not from `eta_seconds >= 0`. The response remains `available` when at least one eligible POI exists and `no_upcoming_pois` otherwise.

Tests must cover:

1. pre-departure before planned departure → calendar-based anticipated ETA;
2. pre-departure after planned departure → positive shifted ETA equal to planned elapsed route duration, not `-1`;
3. active ahead in-flight POI with a stale scheduled timestamp → `upcoming=True`, state `available`, and a current-position estimate;
4. behind-route in-flight POI → `upcoming=False` even with a non-negative ETA;
5. simulation's prompt in-flight transition uses the same estimated path;
6. post-arrival → no upcoming POIs;
7. invalid coordinates/kind remain excluded;
8. endpoint/frontend contract continues to render backend-projected eligible rows rather than filtering valid route POIs by stale ETA.

The browser journey must retain the user-visible KML flow and prove KAAA/KBBB are visible on Overview without API seeding or a synthetic clock.

## Acceptance-platform WebGL2 capability

### Profile authority

The browser profile remains external to the candidate repository and remains the sole launch authority. The verified executable, SHA/version, headed Xvfb mode, loopback CDP, sandbox policy, browser process group, isolated user profile, 1920×1080 viewport, and DPR1 are unchanged.

The platform-owned launch adds exactly:

```text
--use-gl=angle
--use-angle=swiftshader
```

Do not add `--enable-unsafe-swiftshader`. Chromium identifies it as lowering security guarantees. No headless fallback, `--no-sandbox`, device emulation, caller-supplied browser flags, or product-specific browser behavior is permitted.

### Fail-closed WebGL preflight

The neutral health/final browser card must prove before a final build:

- a real `webgl2` context is created;
- renderer/vendor/version identity is captured as bounded evidence;
- page and visual viewport are each 1920×1080 at DPR1;
- the neutral screenshot is decoded and exactly 1920×1080;
- browser/Xvfb diagnostics are retained;
- failure blocks final acceptance before Compose build/startup.

The profile must use the same certified launch path for health and final. A final failure after preflight must retain the first product failure separately from cleanup failure.

## Cleanup evidence correction

Diagnostic cleanup must distinguish its durable evidence root from ephemeral task root. Machine-readable cleanup evidence must name each path explicitly and state whether it is intentionally retained evidence or an ephemeral resource expected absent. It must never report a retained evidence root as an uncleared task root.

## Verification and release gates

After implementation and independent task review:

1. publish the exact feature SHA;
2. run fresh exact-SHA health and static lanes;
3. run one authorized monitored final lane using the profile-owned WebGL2 path;
4. verify the final manifest, artifact checksums, WebGL identity, KAAA/KBBB Overview state, image provenance, and complete cleanup;
5. do not claim final acceptance if a product journey, WebGL preflight, evidence verification, or cleanup predicate fails.

## Documentation impact

Update the acceptance operations guide to document the controlled ANGLE/SwiftShader configuration, neutral WebGL2 preflight, and the fact that the unsafe SwiftShader opt-in is intentionally excluded. Update applicable V2 acceptance documentation to state that Upcoming POI visibility is route-relative and that ETA/schedule values remain metadata.
