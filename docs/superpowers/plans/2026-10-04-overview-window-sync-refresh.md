# Overview Window Synchronization: Saved-State Refresh Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> for native execution, or `superpowers:subagent-driven-development` if
> delegation is selected. Track the checkbox steps below.

**Goal:** Refresh Overview's saved configuration and mission-derived state while
the editing window retains focus, without resetting local view state.

**Architecture:** Each mounted Overview query observer owns its refresh
interval. Existing query keys deduplicate reads. Configuration observers retain
their current defaults and forms; confirmed saves cancel obsolete local reads.

**Tech Stack:** TanStack Query 5, Axios AbortSignal, React, Vitest, Playwright.

**Spec:** [Approved design](../specs/2026-10-04-overview-window-sync-design.md).
Read the [main plan](2026-10-04-overview-window-sync.md) for Global Constraints,
Review Focus, baseline, and execution requirements.

## Task 1: Deliver scoped background refresh

**Files:**

- Create: `src/hooks/api/overview-refresh-options.ts`,
  `src/hooks/api/useOverviewRefresh.test.tsx`.
- Modify: `src/hooks/api/useOverviewClockSettings.ts`,
  `useOverviewHistorySettings.ts`, `useOverviewLinkSettings.ts`, `useRoutes.ts`,
  `useSatellites.ts`, `useOverviewHistory.ts` and their existing unit tests.
- Modify: `src/services/overview-clock-settings.ts`, `overview-history.ts`,
  `routes.ts`, `satellites.ts`; `src/pages/OverviewPage.tsx`.
- Create: `tests/e2e/overview-window-refresh.spec.ts`,
  `tests/e2e/support/overview-window-fixture.ts`.

**Interfaces:**

- Produce `overviewRefreshOptions(live: boolean)`: live returns
  `refetchInterval: 5000`, `refetchIntervalInBackground: true`,
  `refetchOnWindowFocus: 'always'`, `refetchOnReconnect: 'always'`; false
  returns no overrides. Keep the inferred object type valid for useQuery.
- Add `live = false` to `useOverviewClockSettings`,
  `useOverviewHistorySettings`, `useOverviewLinkSettings`, `useRoutes`, and
  `useSatellites`; add `live = false` as useRoute's second parameter.
- Overview calls these hooks with true. Link settings keeps its existing
  five-second foreground polling when false. Empty useRoute IDs stay disabled.
- Add optional `signal?: AbortSignal` to clock/history-settings/history GETs,
  routesApi.list, routesApi.get's second parameter, and satelliteService.getAll.
  Query functions pass their context.signal explicitly to Axios.
- History keeps its existing interval/error rollback and enables background
  polling on its existing observer; never add a second history timer.
- Fixture produces `installOverviewWindowFixture(context: BrowserContext)`
  returning mutable confirmed settings/mission state, read counts, failure/hold
  controls, and a recorded ordered request log shared by both pages.

- [x] **Step 1: Write failing hook and two-page browser regressions.** Use real
      QueryClient observers/fake timers to assert
      clock/history/routes/satellites read again at 5000ms with focusManager
      false; default Configuration clock observers do not acquire periodic
      polling. Assert disabled route, deduped shared-key observers,
      foreground/network recovery, and cleanup. Extend the existing link hook
      test for both live/default modes. Browser assertions:

  ```ts
  const overview = await context.newPage();
  await overview.goto("/overview");
  const editing = await context.newPage();
  await editing.goto("/configuration");
  await editing.bringToFront();
  // Fixture PUT persists the real form's payload and returns success.
  await editing.getByLabel("Clock 3 label").fill("Honolulu operations");
  await editing.getByLabel("Clock 3 timezone").fill("Pacific/Honolulu");
  const saved = editing.waitForResponse(
    (r) =>
      r.url().endsWith("/api/overview-clocks/settings") &&
      r.request().method() === "PUT",
  );
  await editing
    .getByRole("button", { name: "Save operational clocks" })
    .click();
  await saved;
  await expect(
    overview.getByRole("region", {
      name: "Honolulu operations operational clock",
      exact: true,
    }),
  ).toBeVisible({ timeout: 8000 });
  // Assert time text at a fixed observed timestamp uses Pacific/Honolulu.
  ```

  Record response-to-visible latency and assert no Overview navigation/reload.
  Add activate/switch/deactivate fixture cases where route geometry and
  generated POIs change together. Keep canvas identity and a manually moved
  camera stable.

- [x] **Step 2: Observe failures before implementation.** Run
      `npm run test:unit -- src/hooks/api/useOverviewRefresh.test.tsx` and
      `npx playwright test tests/e2e/overview-window-refresh.spec.ts --workers=1`
      from the frontend. Failures must identify missing background reads and
      stale visible state, not fixture/setup failures.
- [x] **Step 3: Implement observer options and signal transport.** Preserve
      existing query keys, enabled flags, retries, default call sites, and
      arrival/status/active-link polling. Use structural sharing; avoid adding
      changing keys to Canvas/chart components or imperative cache clearing.
- [x] **Step 4: Verify hooks and the two-page fixture suite pass.** Include two
      Configuration pages: one has an unsaved clock draft while the other saves;
      polling on Overview must not reset that draft. Reuse camera observation
      helpers and assert retained chart samples through unchanged-window saves.
      Run `npm run test:unit -- src/hooks/api` and `npm run build` as well.
- [x] **Step 5: Commit the scoped refresh deliverable.** Stage only this task's
      listed files; commit `fix(overview): refresh saved state across windows`.

## Task 2: Preserve confirmed state through save/read races and recovery

**Files:**

- Modify: `src/hooks/api/useUpdateOverviewClockSettings.ts`,
  `useUpdateOverviewHistorySettings.ts` and their tests.
- Extend: `src/hooks/api/useOverviewRefresh.test.tsx`,
  `tests/e2e/overview-window-refresh.spec.ts`,
  `tests/e2e/support/overview-window-fixture.ts`.
- Inspect and change only if regression demonstrates a defect:
  `src/pages/OverviewMetricHistoryPanel.tsx`,
  `OperationalClockSettingsForm.tsx`.

**Interfaces:**

- Consume Task 1's AbortSignal-enabled GETs and unchanged query keys.
- Keep mutation argument/result contracts; serialize each settings mutation with
  scope IDs `overview-clock-settings` / `overview-history-settings`.
- Cancel the settings GET inside mutationFn before PUT and again before
  publishing the full successful response with setQueryData. Invalidate the
  settings query afterward; successful history saves also invalidate history.
- A failed PUT never writes submitted values to confirmed cache. Existing link
  mutation cancellation/serialization remains intact.

- [ ] **Step 1: Add behavioral failing race tests.** Use deferred transport
      responses, not mocks of option shapes. Pin these outcomes:

  ```ts
  // A starts before PUT; B starts during PUT; both return old settings.
  expect(readA.signal.aborted).toBe(true);
  expect(readB.signal.aborted).toBe(true);
  expect(client.getQueryData(["overview-clock-settings"])).toEqual(saved);
  // Reject a later PUT: the submitted draft is never confirmed.
  expect(client.getQueryData(["overview-clock-settings"])).toEqual(saved);
  // A mismatched old history bundle cannot masquerade as the new window.
  expect(oldBundle.window_seconds).not.toBe(newSettings.window_seconds);
  ```

  Also cover queued consecutive saves, cancelled read rejection without an
  unhandled promise, failed refresh retaining last confirmed settings, and next
  successful background read catching up without focus. A delayed old route-ID
  detail must not reactivate that route after the list selects another ID.

- [ ] **Step 2: Run affected mutation/hook tests and observe the race
      failures.** Run:

  ```sh
  npm run test:unit -- \
    src/hooks/api/useUpdateOverviewClockSettings.test.ts \
    src/hooks/api/useUpdateOverviewHistorySettings.test.ts \
    src/hooks/api/useOverviewRefresh.test.tsx
  ```

- [ ] **Step 3: Implement scoped cancellation and confirmed-response writes.**
      Follow the existing link mutation pattern. Preserve the chart's existing
      `history.window_seconds === selectedWindowSeconds` check and retention
      behavior; adjust only where the new behavioral regression fails.
- [ ] **Step 4: Verify races, outages, fullscreen continuity, and defaults.**
      Run affected unit tests, link mutation tests, and the refresh browser
      suite. Browser cases include failed PUT, an interrupted GET followed by
      recovery, ordinary/fullscreen views, retained history, and changed
      timezone time text. Cross-window REST convergence is eventual; do not
      invent a global revision or claim endpoint-atomic switching. Run
      `./tools/verify frontend` at root.
- [ ] **Step 5: Commit the confirmed-state deliverable.** Commit
      `fix(overview): preserve confirmed settings through refresh races`.
