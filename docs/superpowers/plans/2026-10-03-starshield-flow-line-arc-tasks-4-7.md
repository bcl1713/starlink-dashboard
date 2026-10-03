# Starshield Flow Line Arc Implementation Plan: Tasks 4–7

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` for recommended native execution, or
> `superpowers:subagent-driven-development` if the user selects delegation.
> Track the checkbox steps below.

**Goal:** Complete activity policies, particle lifecycle, scene integration and
acceptance for the independently controlled production traffic links.

**Architecture:** Consume the settings and globe-safe arc from Tasks 1–3, keep
measured and synthetic activity separate, and integrate through existing pooled
particle rendering and scene guards.

**Tech Stack:** React, TypeScript, React Query, Three.js/React Three Fiber,
Vitest/Testing Library, pytest and Playwright/CDP; no new dependencies.

**Spec:** [Approved traffic arc design](../specs/2026-10-03-overview-traffic-paths-design.md).

## Global constraints and review focus

All [main plan constraints, interfaces and review focus](2026-10-03-starshield-flow-line-arc.md)
apply here. This is one seven-task implementation plan split to respect the
repository's 300-line document limit. Complete Tasks 1–3 first. Product execution
awaits user review of the complete plan.

## Task 4: Independent measured and illustrative activity policies

**Files:** Modify `frontend/mission-planner/src/pages/overview-flow-consumers.ts`
and `.test.ts`. Create `overview-link-state.ts` and `.test.ts` beside it.
Reuse `status-freshness.ts` and metric availability/readout conventions.

**Interfaces:** Export `FlowEmitters = { forward: FlowEmitterConfig;
reverse: FlowEmitterConfig }`, `measuredTrafficFlowEmitters(telemetry:
LinkTelemetry | undefined): FlowEmitters` (rename the old active-link helper),
and `xBandFlowEmitters(active: boolean): FlowEmitters`.
`deriveOverviewLinkState(input: OverviewLinkStateInput): OverviewLinkState`
takes `settings: OverviewLinkSettings | undefined`, `status: StatusResponse |
undefined`, `nowMs: number`, `statusRequestFailed: boolean`,
`hasTrafficGeometry: boolean`, `hasXBandGeometry: boolean`,
`selectionState: 'normal' | 'warning' | null`, and
`selectionRequestFailed: boolean` (selection or catalog unavailable).
It returns `starshieldVisible: boolean`, `xBandVisible: boolean`,
`starshieldFlow: FlowEmitters` and `xBandFlow: FlowEmitters`.

- [ ] Write tests for the four settings pairs, unconfirmed settings, missing PoP,
  invalid aircraft, status age 9,999/10,000 ms, failed requests with cached data
  and existing clock-skew rules. An unavailable/false metric flag or nonfinite,
  negative/zero throughput disables only that direction. Missing/invalid latency
  or loss omits that modulation. Network unavailable with fresh position must
  still animate a normal X-band link; warning/unknown/failed selection stops only
  X-band. Missing PoP/selection affects only its own link.
  Name the preset case `keeps illustrative X-band visible without measured data`:

  ```ts
  const preset = xBandFlowEmitters(true);
  expect(preset.forward.brightness).toBeGreaterThanOrEqual(1.35);
  expect(preset.reverse.rate).toBe(preset.forward.rate);
  expect(preset.forward.failure).toBeUndefined();
  ```

- [ ] Run the focused tests from the frontend:

  ```sh
  npm run test:unit -- src/pages/overview-flow-consumers.test.ts src/pages/overview-link-state.test.ts
  ```

  expect new signatures/eligibility assertions to fail.
- [ ] Implement position age using the original timestamp and request error,
  separately from network flags. Starshield line needs enabled setting, fresh
  valid position and valid arc; network gaps suppress particles only. Preserve
  X-band retained geometry rules, but emit only with fresh geometry and current
  normal selection. Keep logarithmic throughput rate mapping, fixed scene travel
  speed 0.5 and 100/direction cap independent of arc length. Missing latency uses
  neutral size 9.5/brightness 3.4 without a made-up RTT; valid nonnegative latency
  retains the existing modulation. Loss must be available/finite/in [0,100].
  X-band alone uses the 4/4/500 preset, no loss, and brightness floor 1.35 so
  its illustrative activity remains visible. Leave route emitters unchanged.
- [ ] Rerun focused tests plus `status-freshness.test.ts` and
  `overview-metric-readout.test.ts`; require independent activity and no writes
  to status, metric history or operational state.
- [ ] Commit with `fix(overview): separate measured traffic from x-band activity`.

## Task 5: Immediate particle clearing and lifecycle control

**Files:** Modify `frontend/mission-planner/src/pages/AnimatedFlowLine.tsx`,
`.test.tsx`, `overview-animated-flow-line-rendering.ts` and `.test.ts`.

**Interfaces:** Add `FlowParticlePool.clear(direction?: FlowDirection): void`,
clearing counts/remainders and recycling particles. `configure` clears each
direction when its new emitter is disabled. Add optional
`canAnimate?: () => boolean` to `AnimatedFlowLineProps`; default allows existing
consumers. It rechecks operational eligibility using wall-clock time before
every frame and on return from hidden state, including before the next UI tick.

- [ ] Write tests that fill pools, disable a direction, then assert an empty
  matching snapshot and zero draw range immediately; re-enable starts fresh.
  Cover warnings, invalid path, hidden page, reduced motion, changing endpoints,
  repeated toggles/mounts and unmount disposal. Assert no catch-up emission after
  hidden return and no buffer writes/updates while paused. Test route/history
  compatibility and per-direction cap after repeated reconfiguration. Include
  React StrictMode mount/cleanup/remount so disposed resources are not reused.
  Name the clearing case `drops existing particles when a direction stops`;
  after configuring the forward emitter disabled, assert:

  ```ts
  expect(pool.snapshot().filter(p => p.direction === 'forward')).toHaveLength(0);
  ```

- [ ] Run the focused tests from the frontend:

  ```sh
  npm run test:unit -- src/pages/AnimatedFlowLine.test.tsx src/pages/overview-animated-flow-line-rendering.test.ts
  ```

  expect missing clear/lifecycle behavior to fail.
- [ ] Implement clearing on disable, endpoint replacement and eligibility loss;
  zero the draw range in the transition effect, not only the next frame. Listen
  to `visibilitychange`, clear/pause on hide, discard the first resumed frame's
  elapsed delta and clamp active delta to 0.1 seconds. Reduced motion also clears
  pools while retaining line geometry. Allocate particle resources only for an
  active particle branch; dispose that branch on pause/ineligibility and dispose
  line resources on parent disable/unmount. Keep hooks unconditional by extracting
  an internal particle child if needed. Remove listeners in cleanup. Memoize the
  prepared path and reuse typed arrays; do not allocate per frame.
- [ ] Rerun focused tests and ribbon tests; require exact resource disposal and
  listener cleanup across repeated transitions, with no particle resurrection.
- [ ] Commit with `fix(overview): clear flow particles across eligibility changes`.

## Task 6: Integrate links, draw guards and conditional legend

**Files:** Modify `frontend/mission-planner/src/pages/OverviewPage.tsx`,
`OverviewPage.layers.test.tsx`, `OverviewPage.contract.test.ts`,
`OverviewMapLegend.tsx`, `.test.tsx` and `OverviewPage.css`.
Create `overview-traffic-style.ts` for shared traffic line/legend color tokens
and `OverviewPage.traffic.test.tsx` for scene integration assertions.

**Interfaces:** Add `trafficPath: boolean` to `OverviewMapLegendProps`.
`TRAFFIC_PATH_STYLE` exports outer/glow/core `FlowLineLayer`s with a violet core
`#c084fc`, distinct from route amber and X-band blue/red; keep upload/download
colors from Task 4. Keep style dimensions within existing link/ribbon budgets.

- [ ] Write integration tests capturing actual `AnimatedFlowLine` props, not only
  mocked-away Canvas DOM. Assert measured values reach only PoP arc, X-band gets
  only preset values, and all toggle combinations match rendered links/legend.
  Assert warning clears X-band activity while Starshield style/activity remains
  unchanged; disabled X-band warning still appears in existing status/card rules.
  Markers, labels, history, route, metrics and camera props remain present.
  Test initial settings loading, refresh errors, stale position and missing PoP.
- [ ] Run the focused tests from the frontend:

  ```sh
  npm run test:unit -- src/pages/OverviewPage.traffic.test.tsx src/pages/OverviewPage.layers.test.tsx src/pages/OverviewPage.contract.test.ts src/pages/OverviewMapLegend.test.tsx
  ```

  expect new layer/legend contracts to fail.
- [ ] Subscribe once to confirmed settings; memoize the arc using scalar endpoint
  coordinates/altitude rather than entire polled status objects. Skip arc
  construction while Starshield is disabled/unconfirmed or its position is stale;
  both-off performs no link-specific rendering work. Apply Task 4 guards, mount
  each link only when visible, and pass wall-clock `canAnimate`
  callbacks using current query data/error state. These callbacks combine
  captured render eligibility with `isStatusStale(status.timestamp, Date.now())`;
  they do not rebuild geometry, allocate emitters or run React state updates in
  a frame. Use the same visibility guards
  for legend entries. Add `Traffic path` sample with shared style token. Keep
  warning computations, cached marker geometry and camera intent unchanged.
- [ ] Rerun focused tests and Configuration tests; update existing fixtures with
  explicit confirmed settings rather than enabling by default in production.
- [ ] Commit with `feat(overview): render independently controlled traffic links`.

## Task 7: Browser, persistence and rendering acceptance

**Files:** Create `frontend/mission-planner/tests/e2e/overview-traffic-paths.spec.ts`.
Update `overview-planned-satellite-legend.spec.ts` fixtures/expected legend entries
in that directory. Modify `docs/features/overview.md`, `docs/features/system.md`
and `docs/deployment/portainer-ghcr.md`. Keep exact-candidate final evidence
in the existing durable acceptance evidence store; summarize development checks
in the PR description without modifying the candidate after final acceptance.

- [ ] Add browser scenarios for all four toggle combinations, reload, immediate
  navigation/shared-query updates, initial/delayed/failed GET and failed save,
  warning → normal, one missing direction, missing latency/loss, expired status,
  missing PoP and selection failure. Use WebGL painted readiness and screenshots
  at 1920×1080 plus existing mobile/fullscreen layouts. Separate deterministic
  intercepted telemetry cases from real API persistence checks in evidence.
- [ ] Run the browser scenarios from the frontend:

  ```sh
  npx playwright test tests/e2e/overview-traffic-paths.spec.ts tests/e2e/overview-planned-satellite-legend.spec.ts --project=chromium
  ```

  Use an available configured browser; require passing
  assertions and inspect captures for readable opposite-direction activity.
  This development test does not substitute for exact-SHA final acceptance.
- [ ] Document shared settings path/defaults, independent switches, measured arc
  versus illustrative X-band and unchanged collection/status behavior. From root
  run `ACCEPTANCE_POLICY_BASE_SHA=<execution-base-40-hex-SHA> ./tools/verify all`;
  require successful static, backend, frontend tests and production build.
- [ ] Commit tests/docs with
  `test(overview): verify traffic arc and link lifecycle`.
- [ ] On the resulting committed candidate run exact-SHA CDP acceptance through production
  Nginx/backend using the existing acceptance workflow. Follow
  [cloud Docker discovery](../../development/cloud-docker.md) and the
  [acceptance platform workflow](../../operations/acceptance-platform.md),
  preserve actor
  `DOCKER_HOST`/context, and isolate project, ports and persisted data. Real API
  checks save all combinations, restart only the task-owned backend and confirm
  the pair survives without affecting measured status/history. Compare both-off,
  Starshield-only and both-on at 1080p over 60 seconds each; record frame-time
  distributions, draw calls and GPU geometry counts without claiming an unknown
  laptop guarantee. Repeat 20 toggle cycles and 10 mounts; resource counts must
  plateau, disabled links must own no resources, and route/history/camera must
  remain usable. Verify hidden/reduced-motion recovery and capture both-on normal
  and warning views. Record candidate SHA, renderer/hardware, build/daemon
  identity, screenshots, performance deltas and cleanup. An unavailable browser
  or deployment laptop is an explicit verification gap, not a passing result.
  Final acceptance identifies this exact candidate; any subsequent product
  change requires fresh applicable checks. Report outcomes and remaining
  hardware validation without merging or starting orbital work implicitly.
