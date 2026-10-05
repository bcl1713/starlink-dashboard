# Overview precipitation radar overlay implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display automatically updated precipitation on the Overview globe,
controlled by a shared default-off setting on Configuration.

**Architecture:** One application-owned service validates and caches RainViewer
data through bounded, pinned HTTPS exchanges. Browsers acquire complete world
atlases and render a separate Mercator-aware surface, independently of core
dashboard loading and telemetry.

**Tech Stack:** Python 3.11 locally/in production, existing FastAPI/Pydantic,
filelock, dnspython, asyncio, pytest; explicitly declare h11 0.16.x for HTTP
framing. Existing Node 22.22.2, React, React Query, Three.js/React Three Fiber,
Vitest, Testing Library, and Playwright Chromium.

**Spec:**
[Approved design](../specs/2026-10-05-overview-weather-overlay-design.md). Read
the spec and all three plan files before execution.

## Global Constraints

- Configuration → Overview → Weather owns **Precipitation radar**; Overview adds
  no weather toggle, refresh button, settings link, or interactive popup.
- Persist enabled=false and revision=0 by default in
  data/settings/overview-weather.json. Shared saves survive restart and
  missions.
- Settings poll every five seconds while visible; trust expires after 15
  seconds. Radar checks every 300 seconds while enabled and visible.
- Use radar.past only, numeric timestamp-matching paths, exact RainViewer HTTPS
  hosts, 60-second future tolerance, and frames younger than 60 minutes.
- Tile size 512, zoom 2, color 2, options 1_1: 16 tiles, 2048-square atlases.
  Coverage uses 0/0_0 and the integral UTC day token.
- Coverage expires at the next UTC day boundary, at most 24 hours later.
- Metadata success lifetime 300 seconds; failure cooldown 30 seconds, honoring
  longer provider Retry-After up to 300 seconds.
- Cap attempts at 90 per rolling 60 seconds, four active exchanges, and 32
  pending unique acquisitions across the single backend worker.
- Cache at most 48 PNGs and 64 MiB; two admitted radar frames, one coverage
  token.
- One five-second deadline starts before admission/DNS and covers every wire
  read. Writer closure/wait occurs once; cancellation reaping is bounded to one
  second.
- Headers 32 KiB, metadata 128 KiB, PNG body 2 MiB and 512-by-512 IHDR
  dimensions. Preserve public-IP pinning, numeric dialing, original Host/SNI and
  TLS checks.
- Browser image concurrency four; whole-load deadline 45 seconds; one pending
  radar generation. Complete-frame swaps only; no default-on provider work.
- GPU atlases at most 48 MiB, no mipmaps; explicit bitmap/canvas/texture
  cleanup.
- Age through 20 minutes is current; over 20 and under 60 is stale; at 60
  remove. Refresh failure immediately marks retained imagery stale without
  renewing expiry.
- Real UTC weather time is independent of simulation/replay. Preserve core
  globe, routes, labels, camera, metrics, telemetry, CSP, and production
  Dockerfiles.
- Remove the obsolete redirect/service. Retain issue 144 until acceptance
  passes.

## Review Focus

1. Same-value saves and failed atomic replacement: never advance revision or
   damage the previously confirmed setting (Task 1).
2. Cancellation immediately after TLS opens, repeated shutdown, and a second
   subscriber on the same key: close exactly once and preserve surviving demand
   (Tasks 2–3).
3. Coverage changes at UTC midnight during a frame load: reject the expired
   mask, refresh automatically, and never mix cache generations (Tasks 3 and 5).
4. Native bitmap decoding finishing after AbortSignal cancellation: dispose its
   result without publication, including shared coverage still used by a frame
   (Task 5).
5. Browser clock edits and regular settings polls: neither renew old weather nor
   restart the five-minute radar schedule on every five-second settings read
   (Task 5).

## File ownership and contracts

Task documents use B for backend/starlink-location and F for
frontend/mission-planner. All listed paths expand relative to repository root.
No existing large component is refactored beyond named integration anchors.

| Owner              | Files and responsibility                                                                                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Task 1             | B/app/models/overview_weather.py; B/app/services/overview_weather/settings.py: strict DTOs and atomic settings                                                                 |
| Task 2             | `B/app/services/overview_weather/{clock.py,protocol.py,transport.py,__init__.py}`: clocks, bounded HTTP, and stream ownership                                                  |
| Task 3             | B/app/services/overview_weather/admission.py, acquisitions.py, service.py, request.py; B/app/api/overview_weather.py: budgets, leases, frames, disconnects, API                |
| Task 3 integration | B/main.py startup/shutdown/router anchors; F/nginx.conf; removal of obsolete weather.py/weather_radar.py and their redirect tests                                              |
| Task 4             | F/src/services/overview-weather.ts; F/src/hooks/api/useOverviewWeatherSettings.ts and useUpdateOverviewWeatherSettings.ts; F/src/pages/weather/OverviewWeatherSettingsCard.tsx |
| Task 5             | F/src/pages/weather/weather-state.ts, weather-atlas.ts, weather-controller.ts; F/src/hooks/useOverviewWeatherLayer.ts                                                          |
| Task 6             | F/src/pages/weather/weather-projection.ts, weather-textures.ts, OverviewWeatherLayer.tsx, OverviewWeatherStatus.tsx, OverviewWeather.css                                       |
| Task 7             | tools/acceptance/overview-weather/; F/playwright.weather-acceptance.config.ts; F/tests/e2e/overview-weather-production.spec.ts; operator/API docs                              |

Backend wire types are WeatherSettings(enabled, revision),
WeatherSettingsUpdate(enabled), and WeatherManifest with the exact spec fields.
The frontend matches those DTOs. ReadyWeatherManifest narrows ready fields to
nonnull values. Coverage token is a UTC day number, frame URL token is epoch
seconds, and wire times are integer epoch milliseconds.

WeatherClock supplies utc_ms() and monotonic(); backend services and transport
share it. Browser elapsed trust/deadlines use performance.now(); frame age uses
server generated_at_ms plus monotonic elapsed time, never simulation time or a
renewed fetch timestamp. Changing frames preserves their original UTC expiry.

Settings observations pair a DTO with receivedAtMono. Cached PNG keys are (kind,
token, z, x, y), with metadata keyed separately. WeatherAtlasPair owns its radar
canvas and a reference-counted coverage lease. The controller owns canvas
leases; the scene borrows canvases and owns only Three textures/materials.

## Task sequence and commands

1. [Backend Task 1](2026-10-05-overview-weather-overlay-backend.md#task-1-shared-settings):
   strict settings and atomic persistence.
2. [Backend Task 2](2026-10-05-overview-weather-overlay-backend.md#task-2-bounded-https-transport):
   cancellable pinned HTTPS with protocol-aware framing.
3. [Backend Task 3](2026-10-05-overview-weather-overlay-backend.md#task-3-acquisition-service-and-production-api):
   cache/leases, API, lifespan, and Nginx.
4. [Frontend Task 4](2026-10-05-overview-weather-overlay-frontend.md#task-4-configuration-and-shared-settings):
   strict client DTOs, confirmed saves, and Configuration control.
5. [Frontend Task 5](2026-10-05-overview-weather-overlay-frontend.md#task-5-refresh-controller-and-complete-atlases):
   clock/freshness state, automatic acquisition, and complete atlases.
6. [Frontend Task 6](2026-10-05-overview-weather-overlay-frontend.md#task-6-globe-surface-and-passive-status):
   projection, texture ownership, globe integration, and passive status.
7. [Acceptance Task 7](2026-10-05-overview-weather-overlay-frontend.md#task-7-production-acceptance-and-operator-documentation):
   actual Nginx paths, rendered behavior, evidence, and documentation.

For backend RED/GREEN commands, run from B: uv run --with-requirements
requirements.txt pytest followed by the named test paths. The tracked
B/.python-version selects 3.11. Frontend commands run from F: npm run test:unit
-- followed by the named paths. A RED run must fail on the new behavior; GREEN
must exit zero with all selected cases passing.

Before product execution, install/reuse the tracked dependencies in this
worktree, run existing weather API/service and Configuration/Overview layer
baselines, and read the cloud runtime skill's Docker/network references before
containers. Preserve DOCKER_HOST/context and task resource isolation. No
dependency installation or product baseline is claimed by this planning commit.

## Execution and delivery

Use the existing worktree .worktrees/144-overview-weather and branch
feat/144-overview-weather; preserve the primary checkout on dev. PR 278 targets
dev and stays draft until implementation and its reviews/acceptance pass. Each
task has its own RED/GREEN cycle and commit. Only one product writer runs at a
time; interfaces advance in dependency order.

Recommend native execution because the seven tasks share the revision, deadline,
cache, and resource-ownership contracts. A fresh whole-branch reviewer checks
specification and quality/security before acceptance. Subagent execution is also
available with a fresh implementer/reviewer for each task.

The user approved the written specification and implementation plan and selected
native execution on 2026-10-05. Continue through implementation, required CI,
acceptance, and a reviewable dev PR.
