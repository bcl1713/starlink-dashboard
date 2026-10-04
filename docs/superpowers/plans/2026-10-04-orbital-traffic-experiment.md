# Orbital Traffic Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> for native execution, or `superpowers:subagent-driven-development` if the user
> selects delegation. Implement task by task and track the checkbox steps in the
> linked task files.

**Goal:** Evaluate small public constellation sprites and one inferred orbital
Starshield traffic path while retaining the production arc as a usable fallback.

**Architecture:** Extend confirmed shared link settings with an off-by-default
orbital preference. A backend catalog service owns persisted provider state and
visible-viewer demand. A browser worker propagates and routes bounded snapshots;
a batched globe layer displays them alongside one existing measured-flow owner.

**Tech Stack:** FastAPI/Pydantic, httpx, filelock, React 19, React Query,
TypeScript, Three.js/React Three Fiber, satellite.js, pytest, Vitest and the
existing acceptance platform. Add satellite.js only during approved execution,
after checking OMM support, license, browser-worker packaging and provider
policy.

**Spec:**
[Approved orbital design](../specs/2026-10-03-orbital-traffic-experiment-design.md).
Also preserve the
[production contract](../specs/2026-10-03-overview-traffic-paths-design.md).

**Authority:** The user requested planning and an isolated experimental branch
on 2026-10-04. Product implementation awaits plan review. Promotion to `dev`
requires a separate user decision after laptop testing, regardless of CI status.

## Baseline and reconciliation

Started `experiment/261-orbital-traffic` from then-current `dev`,
`b2ea3341f78137c1409a618c8d8da5814a14dac2` (PR #259). Issue #261 points to an
already approved design; there is no new design approval cycle to repeat.

Production now supplies `projectTrafficArc`, `deriveOverviewLinkState`,
`measuredTrafficFlowEmitters`, `AnimatedFlowLine.particleKey`, hidden-page
particle clearing, reduced-motion suppression, persistent independent switches,
and legend draw guards. Reuse these delivered interfaces instead of repeating
the earlier arc plan's work or assuming its pre-implementation baseline.

The scene uses Earth radius `2`, physical reference radius `6,378,137 m`, and
axes `[ECEF x, ECEF z, -ECEF y]`. Aircraft altitude is feet MSL converted by
`0.3048`; satellite propagation returns kilometers. Keep propagation/clearance
in physical Earth-fixed kilometers and scale only at the rendering boundary.

No product code or dependencies are changed by this planning commit. All task
file paths below are relative to the repository root; frontend task paths use
`frontend/mission-planner/`, backend task paths use
`backend/starlink-location/`.

## Branch ownership and synchronization

- Keep all experiment code, its new dependency and evaluation documents on
  `experiment/261-orbital-traffic`. Other feature branches continue from `dev`.
- Check remote `dev` hourly and before each implementation session. If it has
  commits not contained in the experiment, merge `dev` into the experiment with
  a regular merge commit. Never rebase or force-push this shared branch.
- Preserve experimental commits and the default-off setting. Never merge the
  experiment into `dev`, enable auto-merge toward `dev`, close issue #261, or
  treat passing checks as promotion approval.
- A sync must use current remote SHAs, handle a moving head with a fresh fetch,
  and push only the experimental ref without force. A conflict must leave the
  remote branch intact and report the files needing reconciliation. Resolve
  conflicts during an active implementation session, then rerun affected tests.
- After a clean sync, run the available affected checks and record any checks
  that cannot run. Current `lint.yml` targets only `main`/`dev`, so absence of
  CI on this experimental branch does not establish passing checks.
- Disable the synchronization watch if the branch is deleted or the user ends
  the experiment. Missing access must produce a clear blocked report.

## Global constraints

- `Orbital traffic view` is shared, persisted and disabled by default; load/save
  failures retain the last confirmed state, initially off. Saves preserve both
  `starshield_link_enabled` and `x_band_link_enabled`.
- Public Starlink elements provide context, not serving-spacecraft or routing
  knowledge. PoP remains estimated internet egress; its ground leg is abstract.
- No satellite names/IDs, estimate badges, confidence percentages or routing
  annotations on the globe. Preserve configured X-band labels and warnings.
- Keep sprites subordinate at `1920×1080`; preserve camera intent, route,
  history, readouts and metrics. Add `Satellites` to the legend only when drawn.
- One Starshield measured-flow owner: upload toward PoP, download toward
  aircraft; unchanged eligibility, colors and budgets. At most `100` particles
  per direction across the whole path, never per hop.
- At most `16,384` accepted/propagated objects, stable catalog-ID subset on
  overflow. Epoch eligibility: at most `72 hours` old, at most `10 minutes` in
  the future. Expire each object independently.
- Persist last good catalog, acquisition time, object epochs, stable generation
  and upstream attempt time. Coalesce downloads; at most one upstream attempt
  per `two hours`, failures included. Honor longer retry delays. Every non-200 HTTP response
  suspends until explicit operator intervention (reviewed provider policy). No demand means no periodic
  upstream work.
- Propagate once per second at a common UTC instant; route selection at most
  every five seconds. Never propagate every satellite per animation frame.
- Access/egress: greatest elevation above a `ten-degree minimum`; a shared
  satellite gives a single-satellite route. Neighbors: at most `eight` per
  satellite, within `5,000 km`, straight-line clearance at least `80 km`.
- Shortest geometric route on that bounded graph: no repeated nodes, at most
  `eight satellite nodes`, at most `2,048 search expansions`, stable catalog-ID
  tie breaking. Disconnection/invalidity/exhausted budget uses the arc.
- Endpoint hysteresis: improvement of `five degrees` for `two selections`. Route
  hysteresis: `ten percent` shorter for `two selections`. Invalidity bypasses
  hysteresis. Recheck path clearance every one-second snapshot.
- Ordinary motion preserves normalized particle progress. Handovers restart
  without bursts, duplicate paths or interpolation between unrelated spacecraft.
- Off/unconfirmed/Starshield-disabled: no worker, subscription, timers, GPU
  buffers or provider demand. Disable/unmount cancels, disposes and invalidates
  late work. Hidden pages release demand and suspend; resume fresh UTC without
  replay. Reduced motion keeps static geometry without moving/interpolated dots.
- Worker failure latches arc fallback for that mount. Retry only through an
  explicit off/on or later Overview mount. Disconnected routes may retain dots;
  invalid aircraft/PoP suppresses traffic geometry.
- Constellation uses at most `two draw calls`,
  `two snapshots plus one in-flight update`, reusable typed buffers and GPU
  interpolation. No graph/full mesh.
- Do not raise pixel ratio or add full-screen effects. Performance targets:
  sustained `30 FPS`, p95 frame time `≤33 ms`, worker update `<250 ms`, and no
  layer-attributable main-thread task `>50 ms`; measure, do not promise.

## Review focus

1. Concurrent setting edits and late GET completion must not resurrect a
   disabled layer or erase another viewer's visibility switch (Tasks 1 and 5).
2. Restart immediately after a failed download must not reset the provider
   clock; corrupt cache files must not permit repeated upstream requests (Task
   2).
3. Catalog reorder/expiry and rapid PoP or endpoint changes must not interpolate
   unrelated satellites or retain an old route (Tasks 3, 4 and 6).
4. A slow worker or queued response after disable must not allocate a fourth
   snapshot, restore demand, or bring disposed GPU resources back (Tasks 3–5).
5. Maximum-size catalogs, polar/antimeridian geometry and disconnected routes
   must remain bounded and preserve the production view (Tasks 3, 4 and 7).

## Tasks and verification

Read this plan and its spec before either task file. Each task includes a red
test, implementation boundary, green check and commit. Keep new modules focused
and below 300 lines where practical; no unrelated Overview refactor.

1. [Tasks 1–3: settings, catalog, propagation](2026-10-04-orbital-traffic-experiment-tasks-1-3.md).
2. [Tasks 4–7: routing, lifecycle, rendering, acceptance](2026-10-04-orbital-traffic-experiment-tasks-4-7.md).

Run targeted tests after each task. At integration, run `./tools/verify static`,
`./tools/verify backend` and `./tools/verify frontend`, using the merge-base
with fresh `dev` for `ACCEPTANCE_POLICY_BASE_SHA`. Backend code changes also
require a fresh isolated Docker build and health verification using the current
runtime instructions in `AGENTS.md` and `docs/development/cloud-docker.md`.

No new provider request belongs in CI or link checking. Browser acceptance uses
controlled catalogs and existing provisioned browser/platform prerequisites;
missing provisioning is environment-blocked evidence, not an invitation to
replace the acceptance platform. Real-provider validation and deployment-laptop
measurements remain explicit Task 7 gates before any promotion decision.

## Execution handoff

Review the plan before implementation. Native execution is the recommendation:
the seven tasks share strict worker, catalog and rendering interfaces, and this
is an isolated experiment. Delegated execution is available if the user prefers
independent task reviews. No execution approach is selected by this document.
