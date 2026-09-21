# Playwright Harness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Starlink Dashboard Playwright E2E harness start reliably, retain failure diagnostics with no retries, use the configured origin in every migrated route fixture, and provide a deterministic WebGL visual control.

**Architecture:** Keep Playwright's existing production-build preview server. Add small test-only support modules for configured-origin route construction and globe visual readiness, then migrate only the E2E specs with literal `localhost:5173` matchers. Set the startup timeout from an owned cold baseline measurement and keep browser evidence classes explicit in the test names and procedure.

**Tech Stack:** TypeScript, Playwright 1.63.0, Vite preview, React/Three.js E2E fixtures, Node.js 22+.

**Spec:** `docs/superpowers/specs/2026-09-21-playwright-harness-design.md`

## Global Constraints

- Base all work on `dev` commit `4193f453d07138efe1b5b696e46e40798efaf306`; retain one branch and one PR targeting `dev`.
- Do not alter dashboard production behavior, backend APIs, real request construction, or visual design.
- Do not create a custom test-server framework or replace Playwright's `npm run build && npm run preview` web-server topology.
- Do not run a standalone production build immediately before a Playwright command; the configured `webServer` already owns that build.
- Keep `retries: 0`; retain diagnostics through a policy that works without a retry.
- Test fixtures prove browser behavior against fixtures, not real-backend or production-proxy acceptance. A WebGL visual snapshot proves only its declared rendered Chromium fixture state.
- Use `PLAYWRIGHT_PORT=5187` for the portable-origin control. The task-owned server must be cleaned up by Playwright; do not reuse another preview server.
- Record documentation impact in the implementation handoff. Update the Oracle `starlink-dashboard-playwright` procedure after the reviewed behavior is known; no user/operator/runbook/release docs are expected unless the supported command contract changes.
- Keep planning labels out of production source, fixtures, and test names. Preserve the repository formatter, lint, and exact-head CI gates.

## Review Focus

1. **No-retry failure:** a failing first attempt must retain the selected configured diagnostic instead of relying on `on-first-retry`; covered in Task 2.
2. **Configured non-default origin:** both route interception and request assertions must use `http://localhost:5187`, not silently accept `5173`; covered in Tasks 1 and 3.
3. **Query-bearing endpoints:** origin construction must preserve the path while allowing query strings; covered in Task 1 and `api-origin.spec.ts` in Task 3.
4. **Incomplete WebGL paint:** a 200 texture response, visible DOM label, or canvas element must not by itself pass the visual control; covered in Task 4.
5. **Slow healthy cold start:** the timeout must be supported by measured owned startup evidence rather than a guessed constant; covered in Task 2.

---

## File map

- Create `frontend/mission-planner/tests/e2e/support/configured-origin.ts` — central test-only helpers for validated configured-origin strings, exact route globs, and query-aware request matchers.
- Create `frontend/mission-planner/src/test/configured-origin.test.ts` — unit-level Vitest coverage of the Playwright-independent configured-origin helper output.
- Create `frontend/mission-planner/tests/e2e/support/globe-visual-ready.ts` — one test-only helper that waits for a named globe asset, a non-zero canvas box, and an animation frame before screenshot assertion.
- Modify `frontend/mission-planner/playwright.config.ts` — explicit measured startup timeout and no-retry-compatible trace policy.
- Create `frontend/mission-planner/src/test/playwright-config.test.ts` — Vitest characterization of the exported timeout, retry, and trace policy.
- Modify `frontend/mission-planner/tests/e2e/api-origin.spec.ts` — use the configured-origin helper and add the non-default-port route/request control.
- Modify `frontend/mission-planner/tests/e2e/leg-detail-responsive.spec.ts` — replace all literal-origin route patterns with helper calls.
- Modify `frontend/mission-planner/tests/e2e/mission-workflow.spec.ts` — replace all literal-origin route patterns with helper calls.
- Modify `frontend/mission-planner/tests/e2e/overview-globe.spec.ts` — use the globe readiness helper and a fixed Chromium screenshot assertion for one deterministic fixture state.
- Modify `frontend/mission-planner/README.md` — add the reproducible E2E command ladder and state that the configured Playwright server owns the production build.
- Modify the Oracle `starlink-dashboard-playwright` procedure only after implementation and independent review establish the exact final timeout/trace policy and commands.

## Task 1: Add configured-origin helpers and unit coverage

**Files:**
- Create: `frontend/mission-planner/tests/e2e/support/configured-origin.ts`
- Create: `frontend/mission-planner/src/test/configured-origin.test.ts`

**Interfaces:**
- Consumes: a base URL string from Playwright `testInfo.project.use.baseURL`.
- Produces: `configuredOrigin(baseURL: string | undefined): string`, `routeGlob(baseURL: string | undefined, pathname: string): string`, and `requestUrlPattern(baseURL: string | undefined, pathname: string): RegExp`.
- `configuredOrigin` returns a normalized URL origin and throws a clear test-setup error if the configured base URL is absent or not an absolute HTTP(S) URL.
- `routeGlob` returns `<origin><pathname>**` and requires `pathname` to begin with `/`.
- `requestUrlPattern` matches `<origin><pathname>` followed by either `?` or end of URL; it escapes the origin and pathname before constructing the expression.

- [ ] **Step 1: Write failing helper tests**

```ts
import { describe, expect, it } from 'vitest';
import {
  configuredOrigin,
  requestUrlPattern,
  routeGlob,
} from '../../tests/e2e/support/configured-origin';

describe('configured E2E origin helpers', () => {
  it('builds route and request patterns from a supplied non-default port', () => {
    const baseURL = 'http://localhost:5187/';

    expect(configuredOrigin(baseURL)).toBe('http://localhost:5187');
    expect(routeGlob(baseURL, '/api/v2/missions')).toBe(
      'http://localhost:5187/api/v2/missions**'
    );
    expect(requestUrlPattern(baseURL, '/api/v2/missions')).toMatch(
      'http://localhost:5187/api/v2/missions?limit=10'
    );
    expect(requestUrlPattern(baseURL, '/api/v2/missions')).toMatch(
      'http://localhost:5187/api/v2/missions'
    );
    expect(routeGlob('http://localhost:5173', '/api/routes')).toBe(
      'http://localhost:5173/api/routes**'
    );
  });

  it('rejects a missing base URL and a relative route path', () => {
    expect(() => configuredOrigin(undefined)).toThrow(/baseURL/i);
    expect(() => routeGlob('http://localhost:5173', 'api/routes')).toThrow(
      /pathname/i
    );
  });
});
```

- [ ] **Step 2: Run the helper test to verify the missing-module RED**

Run from `frontend/mission-planner`:

```bash
npm run test:unit -- src/test/configured-origin.test.ts
```

Expected: FAIL during collection because `configured-origin.ts` does not exist yet. If the command instead fails because Vitest discovers E2E specs incorrectly, stop and record that harness boundary failure before changing helper code.

- [ ] **Step 3: Implement the minimal helper module**

```ts
function requireAbsoluteBaseURL(baseURL: string | undefined): URL {
  if (!baseURL) {
    throw new Error('Playwright project.use.baseURL must be configured');
  }

  const parsed = new URL(baseURL);
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('Playwright baseURL must use http or https');
  }
  return parsed;
}

export function configuredOrigin(baseURL: string | undefined): string {
  return requireAbsoluteBaseURL(baseURL).origin;
}

export function routeGlob(baseURL: string | undefined, pathname: string): string {
  if (!pathname.startsWith('/')) {
    throw new Error('Route pathname must begin with /');
  }
  return `${configuredOrigin(baseURL)}${pathname}**`;
}

export function requestUrlPattern(
  baseURL: string | undefined,
  pathname: string
): RegExp {
  if (!pathname.startsWith('/')) {
    throw new Error('Route pathname must begin with /');
  }
  const escaped = `${configuredOrigin(baseURL)}${pathname}`.replace(
    /[.*+?^${}()|[\]\\]/g,
    '\\$&'
  );
  return new RegExp(`^${escaped}(?:\\?|$)`);
}
```

Use the repository formatter to settle line wrapping and replace the escape expression only if TypeScript or the regression test proves it malformed.

- [ ] **Step 4: Run focused helper coverage and discovery control**

Run from `frontend/mission-planner`:

```bash
npm run test:unit -- tests/e2e/support/configured-origin.spec.ts
npx playwright test --list --project=chromium
```

Expected: helper test passes; Playwright lists browser specs successfully. Record collected file names/counts and verify the helper test command actually collected the new file.

- [ ] **Step 5: Commit the helper increment**

```bash
git add \
  frontend/mission-planner/tests/e2e/support/configured-origin.ts \
  frontend/mission-planner/src/test/configured-origin.test.ts
git commit -m "test(e2e): add configured origin helpers"
```

## Task 2: Measure and configure startup and diagnostic policy

**Files:**
- Modify: `frontend/mission-planner/playwright.config.ts`
- Modify: `frontend/mission-planner/README.md`
- Create: `frontend/mission-planner/src/test/playwright-config.test.ts`

**Interfaces:**
- Consumes: the existing `PLAYWRIGHT_PORT` configuration and production-build preview command.
- Produces: a numeric `webServer.timeout` selected from owned cold-start evidence and a trace mode that retains diagnostics for failed no-retry runs.

- [ ] **Step 1: Capture the cold-start baseline before configuration changes**

From a clean branch worktree, ensure no unrelated process owns the test port, then run one existing focused browser test:

```bash
cd frontend/mission-planner
ss -ltnp '( sport = :5173 )'
/usr/bin/time -f 'elapsed=%E exit=%x' \
  npx playwright test tests/e2e/api-origin.spec.ts \
  --project=chromium \
  --grep 'loads an empty mission collection' \
  --reporter=line
status=$?
ss -ltnp '( sport = :5173 )'
exit "$status"
```

Expected: record whether page execution begins and the elapsed time. If the run ends with `Timed out waiting 60000ms from config.webServer`, preserve it as the required bootstrap diagnosis; do not retry it or call it product evidence.

- [ ] **Step 2: Write the failing configuration characterization test**

Create `src/test/playwright-config.test.ts` to load the exported Playwright config and assert:

```ts
import { describe, expect, it } from 'vitest';
import config from '../../playwright.config';

function oneWebServer() {
  if (!config.webServer || Array.isArray(config.webServer)) {
    throw new Error('Expected exactly one Playwright webServer configuration');
  }
  return config.webServer;
}

describe('Playwright harness policy', () => {
  it('uses an explicit startup budget and retains no-retry diagnostics', () => {
    expect(oneWebServer()).toMatchObject({
      timeout: expect.any(Number),
    });
    expect(config.use?.trace).toBe('retain-on-failure');
    expect(config.retries).toBe(0);
  });
});
```

Use the repository's existing TypeScript test conventions. The RED must fail because `timeout` is absent and the current trace policy is `on-first-retry`.

- [ ] **Step 3: Implement the measured policy**

Set `webServer.timeout` to a documented constant that exceeds the observed healthy cold baseline with explicit headroom. Set `use.trace` to `retain-on-failure` while retaining `retries: 0`. Do not change worker parallelism, project selection, build command, preview command, or port derivation.

Add a README E2E section that records:

```bash
# From frontend/mission-planner; Playwright performs the production build.
npx playwright test --list --project=chromium
npx playwright test tests/e2e/api-origin.spec.ts --project=chromium --reporter=line
npx playwright test tests/e2e/api-origin.spec.ts --project=chromium --reporter=line
npx playwright test --project=chromium --reporter=line
```

Explain the preflight/focused/affected-spec/final-inventory purposes and state that no standalone `npm run build` precedes Playwright because `webServer.command` already builds.

- [ ] **Step 4: Run the configuration control and one focused browser check**

Run from `frontend/mission-planner`:

```bash
npm run test:unit -- src/test/playwright-config.test.ts
npx playwright test tests/e2e/api-origin.spec.ts \
  --project=chromium \
  --grep 'loads an empty mission collection' \
  --reporter=line
```

Expected: configuration characterization passes and the browser command reaches page execution. Record command, elapsed time, test totals, and whether `playwright-report/` or trace output exists only after an intentionally failed diagnostic run; do not fabricate a failing product fixture solely to create an artifact.

- [ ] **Step 5: Commit the startup and diagnostics increment**

```bash
git add \
  frontend/mission-planner/playwright.config.ts \
  frontend/mission-planner/README.md \
  frontend/mission-planner/src/test/playwright-config.test.ts
git commit -m "test(e2e): harden Playwright bootstrap diagnostics"
```

## Task 3: Migrate literal-origin fixtures and prove the non-default port

**Files:**
- Modify: `frontend/mission-planner/tests/e2e/api-origin.spec.ts`
- Modify: `frontend/mission-planner/tests/e2e/leg-detail-responsive.spec.ts`
- Modify: `frontend/mission-planner/tests/e2e/mission-workflow.spec.ts`

**Interfaces:**
- Consumes: `testInfo.project.use.baseURL` and the helper exports from Task 1.
- Produces: route matchers and request assertions that honor `PLAYWRIGHT_PORT` without changing the API path, request method, fixture payload, or user-visible assertion.

- [ ] **Step 1: Write the failing non-default-port control in `api-origin.spec.ts`**

Add `testInfo` to the first test signature and use the helper in the intended final assertion shape:

```ts
const baseURL = testInfo.project.use.baseURL;
await page.route(routeGlob(baseURL, '/api/v2/missions'), fulfillEmptyMissions);

await page.goto('/missions');
expect(missionRequests[0]).toMatch(
  requestUrlPattern(baseURL, '/api/v2/missions')
);
```

Run the spec with a non-default configured port before migrating the hard-coded route. Expected: the current literal `5173` matcher fails to intercept or the request assertion fails, proving the portable-origin RED.

```bash
PLAYWRIGHT_PORT=5187 npx playwright test tests/e2e/api-origin.spec.ts \
  --project=chromium \
  --grep 'loads an empty mission collection' \
  --reporter=line
```

- [ ] **Step 2: Replace literals in `api-origin.spec.ts`**

Import `routeGlob` and `requestUrlPattern`. Change both mission and export routes to use `routeGlob(testInfo.project.use.baseURL, pathname)` and change their recorded request assertions to use `requestUrlPattern`. Keep the existing fixture bodies, headers, pages, button action, and expectation cardinality unchanged.

- [ ] **Step 3: Migrate responsive and workflow fixture matchers**

In `leg-detail-responsive.spec.ts` and `mission-workflow.spec.ts`, add the minimal `testInfo` plumbing to each test or shared setup function that registers a literal route. Replace every `http://localhost:5173` route pattern with `routeGlob(testInfo.project.use.baseURL, pathname)`. Preserve each existing wildcard suffix and use `requestUrlPattern` only where a test currently asserts a full URL including optional query text.

Run this zero-literal audit before moving on:

```bash
git grep -n 'http://localhost:5173' -- tests/e2e
```

Expected: no results. Do not replace broad `**/api/...` fixture patterns in unrelated specs; they are not part of the literal-origin defect.

- [ ] **Step 4: Run focused migration controls**

Run from `frontend/mission-planner`:

```bash
PLAYWRIGHT_PORT=5187 npx playwright test tests/e2e/api-origin.spec.ts \
  --project=chromium \
  --reporter=line
npx playwright test tests/e2e/leg-detail-responsive.spec.ts \
  --project=chromium \
  --reporter=line
npx playwright test tests/e2e/mission-workflow.spec.ts \
  --project=chromium \
  --reporter=line
```

Expected: the non-default-port invocation executes and all migrated affected specs pass. Record the port-owner check after each command and classify any startup failure separately from an assertion failure.

- [ ] **Step 5: Commit the portable-origin increment**

```bash
git add \
  frontend/mission-planner/tests/e2e/api-origin.spec.ts \
  frontend/mission-planner/tests/e2e/leg-detail-responsive.spec.ts \
  frontend/mission-planner/tests/e2e/mission-workflow.spec.ts
git commit -m "test(e2e): honor configured fixture origin"
```

## Task 4: Add deterministic WebGL visual readiness control

**Files:**
- Create: `frontend/mission-planner/tests/e2e/support/globe-visual-ready.ts`
- Modify: `frontend/mission-planner/tests/e2e/overview-globe.spec.ts`
- Create: `frontend/mission-planner/tests/e2e/overview-globe.spec.ts-snapshots/overview-globe-ready-chromium-linux.png` through Playwright's normal snapshot-generation convention.

**Interfaces:**
- Consumes: a Playwright `Page`, the known local texture pathname `/earth-day-hi.jpg`, and the existing 1920×1080 Overview fixture state.
- Produces: `waitForGlobeVisualReady(page: Page): Promise<Locator>` that waits for the named texture response, a visible canvas with a non-zero bounding box, and one browser animation frame after the canvas is attached.

- [ ] **Step 1: Write the failing readiness-control test**

In the existing anti-meridian Overview fixture, replace the inline texture wait with the intended helper use and add a snapshot assertion against the canvas:

```ts
const canvas = await waitForGlobeVisualReady(page);
await expect(canvas).toHaveScreenshot('overview-globe-ready.png', {
  animations: 'disabled',
});
```

Keep all existing fixture routes and semantic legend/marker assertions. Expected RED: missing helper and missing approved snapshot baseline.

- [ ] **Step 2: Implement the minimal readiness helper**

```ts
import { expect, type Locator, type Page } from '@playwright/test';

export async function waitForGlobeVisualReady(page: Page): Promise<Locator> {
  const texture = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
      response.status() === 200
  );
  const canvas = page.locator('canvas').first();

  await expect(texture).resolves.toBeTruthy();
  await expect(canvas).toBeVisible();
  await expect.poll(async () => {
    const box = await canvas.boundingBox();
    return Boolean(box && box.width > 0 && box.height > 0);
  }).toBe(true);
  await page.evaluate(
    () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  );

  return canvas;
}
```

Start the helper's texture wait before `page.goto()` by accepting a `Promise<Response>` created by the caller if test ordering otherwise makes the response race. Do not add canvas pixel inspection, CSS mutation, synthetic animation, mocked WebGL context, or a test-only paint loop.

- [ ] **Step 3: Generate and review the fixed Chromium snapshot**

Run only the named Overview test at the existing fixed 1920×1080 viewport:

```bash
npx playwright test tests/e2e/overview-globe.spec.ts \
  --project=chromium \
  --grep 'renders an active anti-meridian route from same-origin API data' \
  --update-snapshots \
  --reporter=line
```

Inspect the generated snapshot directly. It must show a non-blank globe canvas at its known fixture state. Treat the image as fixture-backed rendered-browser evidence only; it does not prove real backend, reverse proxy, telemetry, or a different GPU/browser stack.

- [ ] **Step 4: Re-run without snapshot update and run the affected spec**

```bash
npx playwright test tests/e2e/overview-globe.spec.ts \
  --project=chromium \
  --grep 'renders an active anti-meridian route from same-origin API data' \
  --reporter=line
npx playwright test tests/e2e/overview-globe.spec.ts \
  --project=chromium \
  --reporter=line
```

Expected: both commands pass. Record the actual browser viewport, test totals, and that the snapshot is scoped to the declared fixture and Chromium project.

- [ ] **Step 5: Commit the visual-control increment**

```bash
git add \
  frontend/mission-planner/tests/e2e/support/globe-visual-ready.ts \
  frontend/mission-planner/tests/e2e/overview-globe.spec.ts \
  frontend/mission-planner/tests/e2e/overview-globe.spec.ts-snapshots/
git commit -m "test(e2e): add deterministic globe visual control"
```

## Task 5: Run the final candidate gates and publish the PR handoff

**Files:**
- Modify only if required by formatter output from the prior tasks.
- Do not add generated `playwright-report/`, `test-results/`, traces, videos, or ad-hoc screenshots to the repository.

**Interfaces:**
- Consumes: the committed candidate from Tasks 1–4.
- Produces: a clean exact commit, command evidence, and a persistent GitHub PR targeting `dev`.

- [ ] **Step 1: Run mechanical and policy preflight**

From `frontend/mission-planner`:

```bash
npm run lint
npm run test:unit
git diff --check
git grep -n -E 'prettier-ignore|prettier-ignore-start|eslint-disable|@ts-ignore|@ts-expect-error' -- \
  ':!package-lock.json'
```

Expected: lint and unit tests pass; diff check has no output; the policy scan has no newly introduced bypass. If existing output appears, compare it to the `dev` merge base and record it rather than changing unrelated baseline content.

- [ ] **Step 2: Run the final exact-candidate E2E inventory once**

From `frontend/mission-planner`:

```bash
npx playwright test --list --project=chromium
npx playwright test --project=chromium --reporter=line
status=$?
ss -ltnp '( sport = :5173 or sport = :5187 )'
git status --short
exit "$status"
```

Expected: record declared and collected inventory, pass/fail/skip totals, elapsed time, Chromium version, fixture scope, and port cleanup. A failure before page creation is bootstrap evidence; an assertion failure is product/harness evidence; neither may be relabeled as visual acceptance.

- [ ] **Step 3: Inspect staged scope and commit the final candidate**

```bash
git status --short
git diff --name-only origin/dev...HEAD
git diff --check origin/dev...HEAD
git add \
  frontend/mission-planner/playwright.config.ts \
  frontend/mission-planner/tests/e2e \
  frontend/mission-planner/README.md
git diff --cached --name-only
git diff --cached --check
git commit -m "test(e2e): harden bootstrap and visual evidence"
```

Expected: staged paths contain only the harness, test, snapshot, and README changes defined in this plan. Do not amend earlier reviewed commits or include generated browser artifacts.

- [ ] **Step 4: Push and open one persistent PR**

```bash
git push --set-upstream origin chore/issue-163-playwright-harness
gh pr create \
  --repo bcl1713/starlink-dashboard \
  --base dev \
  --head chore/issue-163-playwright-harness \
  --title 'test(e2e): harden Playwright bootstrap and visual evidence' \
  --body $'Closes #163\n\n## Harness changes\n- Measured web-server startup timeout: replace this line with the measured numeric constant before submission.\n- No-retry diagnostics: `trace: retain-on-failure`, with `retries: 0`.\n- Portable fixtures: every migrated literal-origin matcher now derives from Playwright baseURL; `PLAYWRIGHT_PORT=5187` is covered.\n- WebGL evidence: the fixed Chromium snapshot is fixture-backed rendered-browser evidence only, not real-backend or production-proxy acceptance.\n\n## Documentation impact\n- Updated frontend E2E command ladder; no operator, user, runbook, or release documentation impact.\n\n## Evidence\n- Replace this line with literal commands, results, and the final commit SHA before submission.'
```

The PR body must link `Closes #163`, list the measured timeout and diagnostics policy, name the exact non-default-port control, state the precise WebGL evidence classification, record documentation impact, and distinguish local fixture/browser evidence from real-backend or production-proxy acceptance.

- [ ] **Step 5: Read back exact-head GitHub evidence and route review**

```bash
gh pr view --repo bcl1713/starlink-dashboard \
  --json url,state,isDraft,baseRefName,headRefName,headRefOid,statusCheckRollup
```

Expected: PR base is `dev`, head is `chore/issue-163-playwright-harness`, and `headRefOid` equals the pushed final commit. Wait for applicable exact-head checks to complete, then route a separate independent review card. The review must verify the measured timeout, no-retry diagnostic policy, complete literal-origin migration, non-default-port control, visual snapshot classification, documentation impact, and absence of generated artifacts.

## Plan self-review

- **Spec coverage:** Task 1 implements portable helper contracts; Task 2 measures and configures startup/diagnostics; Task 3 migrates all baseline literal-origin specs and proves port `5187`; Task 4 establishes the bounded WebGL visual control; Task 5 records documentation impact, exact-head checks, PR creation, and independent review routing.
- **Evidence value scan:** Every implementation path, test path, snapshot path, and publication command is named. Before PR creation, replace the measured-timeout and final-evidence sentences in the PR body with values generated by the prescribed runs; those values do not exist until the runs complete.
- **Type consistency:** Task 1 defines the names consumed by Task 3. Task 4 defines the page-to-canvas helper consumed by `overview-globe.spec.ts`.
- **Review Focus coverage:** Task 2 covers no-retry diagnostics and startup measurement; Task 1 and Task 3 cover default/non-default/query origin behavior; Task 4 covers WebGL evidence classification.
