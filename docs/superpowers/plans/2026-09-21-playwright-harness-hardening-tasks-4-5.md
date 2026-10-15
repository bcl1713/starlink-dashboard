# Playwright Harness Hardening: Tasks 4-5

## Task 4: Add deterministic WebGL visual readiness control

**Files:**

- Create: `frontend/mission-planner/tests/e2e/support/globe-visual-ready.ts`
- Modify: `frontend/mission-planner/tests/e2e/overview-globe.spec.ts`
- Create:
  `frontend/mission-planner/tests/e2e/overview-globe.spec.ts-snapshots/overview-globe-ready-chromium-linux.png`
  through Playwright's normal snapshot-generation convention.

**Interfaces:**

- Consumes: a Playwright `Page`, the known local texture pathname
  `/earth-day-hi.jpg`, and the existing 1920×1080 Overview fixture state.
- Produces: `waitForGlobeVisualReady(page: Page): Promise<Locator>` that waits
  for the named texture response, a visible canvas with a non-zero bounding box,
  and one browser animation frame after the canvas is attached.

- [ ] **Step 1: Write the failing readiness-control test**

In the existing anti-meridian Overview fixture, replace the inline texture wait
with the intended helper use and add a snapshot assertion against the canvas:

```ts
const canvas = await waitForGlobeVisualReady(page);
await expect(canvas).toHaveScreenshot("overview-globe-ready.png", {
  animations: "disabled",
});
```

Keep all existing fixture routes and semantic legend/marker assertions. Expected
RED: missing helper and missing approved snapshot baseline.

- [ ] **Step 2: Implement the minimal readiness helper**

```ts
import { expect, type Locator, type Page } from "@playwright/test";

export async function waitForGlobeVisualReady(page: Page): Promise<Locator> {
  const texture = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/earth-day-hi.jpg" &&
      response.status() === 200,
  );
  const canvas = page.locator("canvas").first();

  await expect(texture).resolves.toBeTruthy();
  await expect(canvas).toBeVisible();
  await expect
    .poll(async () => {
      const box = await canvas.boundingBox();
      return Boolean(box && box.width > 0 && box.height > 0);
    })
    .toBe(true);
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
  );

  return canvas;
}
```

Start the helper's texture wait before `page.goto()` by accepting a
`Promise<Response>` created by the caller if test ordering otherwise makes the
response race. Do not add canvas pixel inspection, CSS mutation, synthetic
animation, mocked WebGL context, or a test-only paint loop.

- [ ] **Step 3: Generate and review the fixed Chromium snapshot**

Run only the named Overview test at the existing fixed 1920×1080 viewport:

```bash
npx playwright test tests/e2e/overview-globe.spec.ts \
  --project=chromium \
  --grep 'renders an active anti-meridian route from same-origin API data' \
  --update-snapshots \
  --reporter=line
```

Inspect the generated snapshot directly. It must show a non-blank globe canvas
at its known fixture state. Treat the image as fixture-backed rendered-browser
evidence only; it does not prove real backend, reverse proxy, telemetry, or a
different GPU/browser stack.

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

Expected: both commands pass. Record the actual browser viewport, test totals,
and that the snapshot is scoped to the declared fixture and Chromium project.

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
- Do not add generated `playwright-report/`, `test-results/`, traces, videos, or
  ad-hoc screenshots to the repository.

**Interfaces:**

- Consumes: the committed candidate from Tasks 1–4.
- Produces: a clean exact commit, command evidence, and a persistent GitHub PR
  targeting `dev`.

- [ ] **Step 1: Run mechanical and policy preflight**

From `frontend/mission-planner`:

```bash
npm run lint
npm run test:unit
git diff --check
git grep -n -E 'prettier-ignore|prettier-ignore-start|eslint-disable|@ts-ignore|@ts-expect-error' -- \
  ':!package-lock.json'
```

Expected: lint and unit tests pass; diff check has no output; the policy scan
has no newly introduced bypass. If existing output appears, compare it to the
`dev` merge base and record it rather than changing unrelated baseline content.

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

Expected: record declared and collected inventory, pass/fail/skip totals,
elapsed time, Chromium version, fixture scope, and port cleanup. A failure
before page creation is bootstrap evidence; an assertion failure is
product/harness evidence; neither may be relabeled as visual acceptance.

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

Expected: staged paths contain only the harness, test, snapshot, and README
changes defined in this plan. Do not amend earlier reviewed commits or include
generated browser artifacts.

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

The PR body must link `Closes #163`, list the measured timeout and diagnostics
policy, name the exact non-default-port control, state the precise WebGL
evidence classification, record documentation impact, and distinguish local
fixture/browser evidence from real-backend or production-proxy acceptance.

- [ ] **Step 5: Read back exact-head GitHub evidence and route review**

```bash
gh pr view --repo bcl1713/starlink-dashboard \
  --json url,state,isDraft,baseRefName,headRefName,headRefOid,statusCheckRollup
```

Expected: PR base is `dev`, head is `chore/issue-163-playwright-harness`, and
`headRefOid` equals the pushed final commit. Wait for applicable exact-head
checks to complete, then route a separate independent review card. The review
must verify the measured timeout, no-retry diagnostic policy, complete
literal-origin migration, non-default-port control, visual snapshot
classification, documentation impact, and absence of generated artifacts.

## Plan self-review

- **Spec coverage:** Task 1 implements portable helper contracts; Task 2
  measures and configures startup/diagnostics; Task 3 migrates all baseline
  literal-origin specs and proves port `5187`; Task 4 establishes the bounded
  WebGL visual control; Task 5 records documentation impact, exact-head checks,
  PR creation, and independent review routing.
- **Evidence value scan:** Every implementation path, test path, snapshot path,
  and publication command is named. Before PR creation, replace the
  measured-timeout and final-evidence sentences in the PR body with values
  generated by the prescribed runs; those values do not exist until the runs
  complete.
- **Type consistency:** Task 1 defines the names consumed by Task 3. Task 4
  defines the page-to-canvas helper consumed by `overview-globe.spec.ts`.
- **Review Focus coverage:** Task 2 covers no-retry diagnostics and startup
  measurement; Task 1 and Task 3 cover default/non-default/query origin
  behavior; Task 4 covers WebGL evidence classification.
