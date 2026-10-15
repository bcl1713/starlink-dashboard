# Playwright Harness Hardening Implementation Plan

**Goal:** Make the Starlink Dashboard Playwright E2E harness start reliably,
retain failure diagnostics with no retries, use the configured origin in every
migrated route fixture, and provide a deterministic WebGL visual control.

**Architecture:** Keep Playwright's existing production-build preview server.
Add small test-only support modules for configured-origin route construction and
globe visual readiness, then migrate only the E2E specs with literal
`localhost:5173` matchers. Set the startup timeout from an owned cold baseline
measurement and keep browser evidence classes explicit in the test names and
procedure.

**Tech Stack:** TypeScript, Playwright 1.63.0, Vite preview, React/Three.js E2E
fixtures, Node.js 22+.

**Spec:** `docs/superpowers/specs/2026-09-21-playwright-harness-design.md`

## Global Constraints

- Base all work on `dev` commit `4193f453d07138efe1b5b696e46e40798efaf306`;
  retain one branch and one PR targeting `dev`.
- Do not alter dashboard production behavior, backend APIs, real request
  construction, or visual design.
- Do not create a custom test-server framework or replace Playwright's
  `npm run build && npm run preview` web-server topology.
- Do not run a standalone production build immediately before a Playwright
  command; the configured `webServer` already owns that build.
- Keep `retries: 0`; retain diagnostics through a policy that works without a
  retry.
- Test fixtures prove browser behavior against fixtures, not real-backend or
  production-proxy acceptance. A WebGL visual snapshot proves only its declared
  rendered Chromium fixture state.
- Use `PLAYWRIGHT_PORT=5187` for the portable-origin control. The task-owned
  server must be cleaned up by Playwright; do not reuse another preview server.
- Record documentation impact in the implementation handoff. Update the Oracle
  `starlink-dashboard-playwright` procedure after the reviewed behavior is
  known; no user/operator/runbook/release docs are expected unless the supported
  command contract changes.
- Keep planning labels out of production source, fixtures, and test names.
  Preserve the repository formatter, lint, and exact-head CI gates.

## Review Focus

1. **No-retry failure:** a failing first attempt must retain the selected
   configured diagnostic instead of relying on `on-first-retry`; covered in
   Tasks 1 and 2.
2. **Configured non-default origin:** both route interception and request
   assertions must use `http://localhost:5187`, not silently accept `5173`;
   covered in Tasks 1 and 3.
3. **Query-bearing endpoints:** origin construction must preserve the path while
   allowing query strings; covered in Task 1 and `api-origin.spec.ts` in Task 3.
4. **Incomplete WebGL paint:** a 200 texture response, visible DOM label, or
   canvas element must not by itself pass the visual control; covered in Task 4.
5. **Slow healthy cold start:** the timeout must be supported by measured owned
   startup evidence rather than a guessed constant; covered in Task 2.

## File Map

- `frontend/mission-planner/tests/e2e/support/configured-origin.ts`
- `frontend/mission-planner/src/test/configured-origin.test.ts`
- `frontend/mission-planner/tests/e2e/support/globe-visual-ready.ts`
- `frontend/mission-planner/playwright.config.ts`
- `frontend/mission-planner/src/test/playwright-config.test.ts`
- `frontend/mission-planner/tests/e2e/api-origin.spec.ts`
- `frontend/mission-planner/tests/e2e/leg-detail-responsive.spec.ts`
- `frontend/mission-planner/tests/e2e/mission-workflow.spec.ts`
- `frontend/mission-planner/tests/e2e/overview-globe.spec.ts`
- `frontend/mission-planner/README.md`

## Task Documents

- [Tasks 1-2: configured origin and harness policy](2026-09-21-playwright-harness-hardening-tasks-1-2.md)
- [Task 3: fixture migration](2026-09-21-playwright-harness-hardening-task-3.md)
- [Tasks 4-5: WebGL control and delivery](2026-09-21-playwright-harness-hardening-tasks-4-5.md)

The task documents preserve the approved implementation steps, commands, and
self-review material. This index keeps the plan under the repository's 300-line
documentation limit while retaining a reviewable navigation point.
