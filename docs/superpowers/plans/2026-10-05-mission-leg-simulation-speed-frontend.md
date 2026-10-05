# Simulation Speed Plan: Frontend Task

Read the [main plan](2026-10-05-mission-leg-simulation-speed.md) and completed
[integration contracts](2026-10-05-mission-leg-simulation-speed-integration.md).

Read the [timing interfaces](2026-10-05-mission-leg-simulation-speed-timing.md)
too.

## Task 5: Controls and Overview presentation

**Files:** Under `frontend/mission-planner/`, create:

- `src/services/simulation-run.ts`: Zod wire validation and API client.
- `src/services/simulation-run.test.ts`: request/response contract tests.
- `src/hooks/api/useSimulationRun.ts`: shared run query and acceptance guard.
- `src/hooks/api/useSimulationRun.test.tsx`: polling/race/restart tests.
- `src/components/missions/SimulateLegDialog.tsx`: mode/input/preview/start
  flow.
- `src/components/missions/SimulateLegDialog.test.tsx`: accessible control
  contracts.
- `src/pages/simulation-run-projection.ts`: real-age and simulated-clock
  projection.
- `src/pages/simulation-run-projection.test.ts`: domain/correction tests.
- `src/pages/SimulationRunPanel.tsx` and `src/pages/SimulationRunPanel.css`:
  running/terminal status presentation.
- `src/pages/SimulationRunPanel.test.tsx`: mode/progress/error/freshness labels.
- `src/pages/OverviewPage.simulation.test.tsx`: network visibility and clock
  wiring.

Modify `src/services/missions.ts`, `src/hooks/api/useMissions.ts`,
`src/hooks/api/useMissions.test.ts`, `src/pages/MissionDetailPage.tsx`,
`src/pages/OverviewPage.tsx`, `src/pages/OverviewClockPanel.tsx`,
`src/pages/overview-arrival.ts`, `src/pages/overview-upcoming-pois.ts`,
`src/services/overview-upcoming-pois.ts`,
`src/hooks/api/useOverviewUpcomingPois.ts`, and
`src/pages/OverviewOverlayLayout.css` only where the replacement layout needs
it. Extend current arrival/clock tests rather than duplicate their behavior.

**Interfaces:**

- Export main-plan wire types plus Task 4's `MissionTimeContext` in the service.
- `simulationRunApi.get(signal?: AbortSignal): Promise<SimulationRunStatus>`.
- `simulationRunApi.preview`:

  ```typescript
  simulationRunApi.preview(missionId: string, legId: string, pacing: PacingInput, signal?: AbortSignal): Promise<SimulationPreview>
  ```

- `simulationRunApi.route(runId: string, signal?: AbortSignal)` returns
  validated `{runtime_id, run_id, route: RouteDetail}`. Query once per confirmed
  runtime/run key; use effective geometry in Overview only when identities
  match. Preserve the ordinary route/history query and restore its geometry
  after cancellation.
- Extend
  `missionsApi.activateLeg(missionId, legId, simulation?: SimulationStart)` with
  typed activation response; old two-argument callers still work.
- `createRunResponseGuard()` provides `beginRequest(): number`,

  ```typescript
  accept(sequence: number, status: SimulationRunStatus): SimulationRunStatus | null
  ```

  , and `confirmMutation(status: SimulationRunStatus): void`. Keep one per query
  client; newer successful mutations invalidate earlier request generations.

- `useSimulationRun()` owns query key `['simulation-run']`, 1000 ms polling,
  `refetchIntervalInBackground: true`, foreground/reconnect refresh, no retries,
  and AbortSignal cancellation. All consumers in a window share that key.
- `useActivateLeg` accepts optional simulation settings, cancels obsolete run
  reads before mutation, installs confirmed status on success, and invalidates
  affected mission/route/clock/POI queries. Failed start retains confirmed
  state.
- `SimulateLegDialog({missionId, legId, open, onOpenChange})` owns only draft
  pacing/preview, not confirmed active state. Read service mode from the run
  query.
- `projectMissionTime`:

  ```typescript
  projectMissionTime(status: SimulationRunStatus | undefined, receivedMonotonicMs: number, monotonicNowMs: number, realNowMs: number, refreshFailed: boolean, previousDisplayTimeMs?: number): number
  ```

  returns the capped simulated clock while running, real time otherwise. Track
  the prior displayed value only within the same run so corrections never rewind
  it.

- `SimulationRunPanel({status, stale, compact})` displays confirmed mode,
  multiplier, simulated progress/time, expected elapsed runtime, terminal result
  and error.
- Extend

  ```typescript
  deriveArrivalPanel(
    response,
    realNowMs,
    refreshFailed,
    (missionNowMs = realNowMs),
  );
  ```

  and `overviewPoiView`'s time-dependent projection with separate real/mission
  clocks. Freshness always uses real time; urgency uses mission time. Add
  optional response `mission_time` without changing legacy data.

- Extend `useOverviewUpcomingPois(pacedRun = false)` to use 1000 ms during
  running paced replay and its existing 5000 ms otherwise; preserve one shared
  query.

- [ ] **Step 1: Write failing UI/contract tests.** Pin representative
      assertions:

```typescript
it("submits only the selected mode after a current preview", async () => {
  await chooseTargetRuntime("120");
  await previewAndStart();
  expect(activateLeg).toHaveBeenCalledWith(missionId, legId, {
    pacing: { mode: "target_runtime", runtime_seconds: 120 },
    plan_token: confirmedPreview.plan_token,
  });
});
it("hides the complete rail only during a confirmed paced run", () => {
  const view = renderOverviewWithRun(runningStatus);
  expect(screen.queryByLabelText("Overview metric history")).toBeNull();
  expect(screen.getByLabelText("Simulation run")).toBeVisible();
  expect(view.canvasIdentity()).toBe(view.initialCanvasIdentity);
  view.confirm(completedStatus);
  expect(screen.getByLabelText("Overview metric history")).toBeVisible();
  expect(view.aircraftTrail()).not.toHaveLength(0);
});
```

Declare these helpers in their owning test files using existing query/client and
Overview fixture patterns; assertions compare rendered output and real requests.
`rejects invalid wire schemas` covers state/run consistency, bad timestamps,
nonfinite/out-of-range numbers, unknown fields, and phase/progress
contradictions. `ignores obsolete preview responses` edits inputs/leg while
preview is in flight. `retains draft and confirmed run on failed start` checks
inline errors and retry.
`allows keyboard preview and start with labeled field errors` checks
focus/Escape, dialog description, and Enter without duplicate activation. Test
mode unknown/live, presets/custom 0.1/1000 limits, preview expiry, unsupported
runtime, and bodyless Activate.

`ignores old-run and old-incarnation responses after restart` uses deferred
promises and mutation confirmation; never compare revisions across runtime IDs.
`two mounted consumers share one polling query` checks call
counts/unmount/foreground cleanup.
`freezes simulated labels on failure or ten-second silence` uses monotonic fake
time, old planned dates, UTC jumps, arrival cap, same-run corrections, and
resume. Confirm completed clocks return to real time while terminal flight
values stay fixed. Test network restoration for cancellation/failure/idle, last
confirmed hiding on refresh error, all five cards/header absent, retained
history query/trail, and no Canvas remount or follow-preference change. ADS-B
and status age use real time. `uses matching effective splice geometry` compares
rendered route/marker positions to the seeded derived route; obsolete geometry
responses cannot replace a new run.

- [ ] **Step 2: Run red.** From frontend root:

  ```bash
  npm run test:unit -- src/services/simulation-run.test.ts src/hooks/api/useSimulationRun.test.tsx src/components/missions/SimulateLegDialog.test.tsx src/pages/simulation-run-projection.test.ts src/pages/SimulationRunPanel.test.tsx src/pages/OverviewPage.simulation.test.tsx
  ```

  Expect missing contracts or failed assertions; record the actual red evidence.

- [ ] **Step 3: Implement the defined interfaces.** Provide an explicit Preview
      action and enable Start only for the current successful preview;
      input/mode/leg changes invalidate it. Keep the dialog draft on error.
      Validate API numbers, never fabricate a confirmed rate from the draft.
      Guard request generations, cancellation and revisions; backend GET
      responses use no-store caching. Use server `served_at - observed_at` plus
      local monotonic age for running silence detection, so browser/server
      wall-clock skew cannot certify stale data. Use real time for source
      freshness and simulated time only for mission labels. Unmount the network
      rail while running, preserve shared history/Canvas, and render terminal
      status outside the restored rail. In-place layout changes preserve
      camera/follow intent in desktop, responsive and fullscreen views.
- [ ] **Step 4: Run green and regressions.** Repeat focused tests plus existing
      `useMissions.test.ts`, `useOverviewRefresh.test.tsx`,
      `overview-arrival.test.ts`, `OverviewClockPanel.test.tsx`, and Overview
      history/traffic unit contracts. Run `npm run test:unit`, `npm run build`,
      and `npm run lint`; expected all pass. Record existing warnings with scope
      rather than suppress them.
- [ ] **Step 5: Commit**
      `feat: add paced simulation controls and Overview state`.
