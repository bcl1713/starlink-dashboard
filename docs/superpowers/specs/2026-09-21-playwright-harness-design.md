# Playwright Harness Hardening Design

## Purpose

Harden the Starlink Dashboard Playwright E2E harness so a clean, owned browser invocation reaches page execution when the production build is healthy, preserves useful failure diagnostics, supports isolated configured ports, and states WebGL visual evidence honestly.

This design implements GitHub issue #163. It is a dedicated test-harness change and must not alter operational-clock work, product behavior, backend APIs, or dashboard feature scope.

## Current state

The `dev` baseline is `4193f453d07138efe1b5b696e46e40798efaf306`.

`frontend/mission-planner/playwright.config.ts` already derives `baseURL` and the preview port from `PLAYWRIGHT_PORT`, defaulting to `5173`. Its `webServer.command` performs `npm run build && npm run preview`, but it has no explicit startup timeout. It also uses `retries: 0` with `trace: 'on-first-retry'`, which does not normally retain a trace for a single failed attempt.

Multiple E2E specs retain literal `http://localhost:5173` route matchers. Those matchers break the configured-port contract even though the Playwright server and browser base URL honor it.

## Goals

1. Set and document an explicit Playwright web-server startup timeout based on a measured cold production-build-and-preview baseline.
2. Retain deliberate, bounded diagnostics for a failed browser invocation when retries remain disabled.
3. Make every affected E2E route fixture derive its origin from the configured Playwright base URL.
4. Prove one owned non-default-port invocation reaches page execution and routes fixtures correctly.
5. Establish a deterministic WebGL readiness and visual-evidence control that is distinct from fixture-backed DOM or transport assertions.
6. Preserve a reproducible command ladder: preflight, one focused test, affected spec, then final exact-SHA inventory run.

## Non-goals

- Do not change dashboard production behavior, backend routes, API schemas, or visual design.
- Do not replace fixture-backed E2E tests with live-backend acceptance.
- Do not treat an HTTP response, DOM marker, canvas existence, or texture dimensions as proof of visible GPU paint.
- Do not create a custom test-server framework or change the existing production-build preview topology without a separately approved design.
- Do not fold this work into PR #162 or any feature PR.

## Architecture

### Config and startup budget

The current Playwright-owned build-and-preview command remains the sole production-build path for E2E execution. Before selecting a timeout value, the implementation measures an owned cold invocation from a clean worktree. The configured timeout must exceed the observed healthy startup with reasonable headroom and be documented alongside the command ladder. A bootstrap timeout before page creation is classified as harness infrastructure failure, not product evidence.

### Failure diagnostics

The harness retains a deliberate diagnostics policy compatible with zero retries. The selected trace/report policy must retain the configured failure evidence without silently adding retry behavior. Diagnostic retention is bounded and must not be described as product acceptance.

### Portable fixture origin

A small E2E support utility owns construction of route patterns from the Playwright configured base URL. Specs use this utility rather than embedding `localhost:5173`. It must support both exact path routes and query-aware patterns without changing the API path or fixture response semantics. The utility is test-scoped and does not change production request construction.

### WebGL evidence classification

The harness adds a deterministic readiness/visual control for the WebGL globe. It must identify what it proves and what it does not prove:

- Fixture-backed route and DOM assertions prove the browser application behavior against declared fixtures.
- The readiness/visual control proves only its documented rendered state under its configured browser and assets.
- Production reverse-proxy plus real-backend visual acceptance remains a separate feature-PR gate when required.

The control must not mutate production layout, paint, pointer-event, or WebGL behavior to manufacture a pass. It should retain bounded screenshot/measurement evidence only where the test contract requires it.

## Test and acceptance matrix

- A baseline measurement records the cold command, elapsed startup behavior, and whether page execution began.
- A failure-diagnostic test or configuration control verifies that a no-retry failure retains the selected configured evidence.
- Origin-helper tests cover default and supplied non-default base URLs, exact routes, and query-aware routes.
- One non-default-port E2E control runs with an owned `PLAYWRIGHT_PORT` and verifies the intended fixture request is intercepted and the target page executes.
- The affected E2E specs run once after migration; the final candidate runs the exact configured Chromium inventory once.
- WebGL readiness/visual acceptance records the actual browser viewport and classifies its result without upgrading fixture, DOM, or transport signals into GPU-paint or real-backend proof.
- The command ladder documentation is verified from a clean checkout and names that Playwright already owns the production build, so no duplicate standalone build precedes its final run.

## Delivery and documentation impact

Implementation uses one isolated branch from `dev` and one persistent PR targeting `dev`. The implementation card records the documentation impact. Expected documentation scope is the Oracle `starlink-dashboard-playwright` procedure; no operator, user, runbook, or release documentation is expected unless the implementation changes the supported operational test command or retention policy beyond the procedure.

The PR requires exact-head applicable CI, independent specification and quality review, and the documented harness evidence before merge/verify. Any browser evidence remains tied to the exact immutable PR head. `main` remains a separate Brian-reviewed release gate.

## Risks and decisions

- The startup timeout value is intentionally deferred until measured; a plausible constant is not evidence.
- Portability migration must cover all literal-origin matchers, not only the spec used for the non-default-port control.
- A successful WebGL readiness control does not waive feature-specific real-runtime visual acceptance.
- The implementation must not use an unrelated already-running preview server or the dirty canonical checkout as evidence.
