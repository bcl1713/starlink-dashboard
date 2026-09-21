# Playwright Harness Hardening: Tasks 3-5

## Task 3: Migrate literal-origin fixtures and prove the non-default port

**Files:**

- Modify: `frontend/mission-planner/tests/e2e/api-origin.spec.ts`
- Modify: `frontend/mission-planner/tests/e2e/leg-detail-responsive.spec.ts`
- Modify: `frontend/mission-planner/tests/e2e/mission-workflow.spec.ts`

**Interfaces:**

- Consumes: `testInfo.project.use.baseURL` and the helper exports from Task 1.
- Produces: route matchers and request assertions that honor `PLAYWRIGHT_PORT`
  without changing the API path, request method, fixture payload, or
  user-visible assertion.

- [ ] **Step 1: Write the failing non-default-port control in
      `api-origin.spec.ts`**

Add `testInfo` to the first test signature and use the helper in the intended
final assertion shape:

```ts
const baseURL = testInfo.project.use.baseURL;
await page.route(routeGlob(baseURL, "/api/v2/missions"), fulfillEmptyMissions);

await page.goto("/missions");
expect(missionRequests[0]).toMatch(
  requestUrlPattern(baseURL, "/api/v2/missions"),
);
```

Run the spec with a non-default configured port before migrating the hard-coded
route. Expected: the current literal `5173` matcher fails to intercept or the
request assertion fails, proving the portable-origin RED.

```bash
PLAYWRIGHT_PORT=5187 npx playwright test tests/e2e/api-origin.spec.ts \
  --project=chromium \
  --grep 'loads an empty mission collection' \
  --reporter=line
```

- [ ] **Step 2: Replace literals in `api-origin.spec.ts`**

Import `routeGlob` and `requestUrlPattern`. Change both mission and export
routes to use `routeGlob(testInfo.project.use.baseURL, pathname)` and change
their recorded request assertions to use `requestUrlPattern`. Keep the existing
fixture bodies, headers, pages, button action, and expectation cardinality
unchanged.

- [ ] **Step 3: Migrate responsive and workflow fixture matchers**

In `leg-detail-responsive.spec.ts` and `mission-workflow.spec.ts`, add the
minimal `testInfo` plumbing to each test or shared setup function that registers
a literal route. Replace every `http://localhost:5173` route pattern with
`routeGlob(testInfo.project.use.baseURL, pathname)`. Preserve each existing
wildcard suffix and use `requestUrlPattern` only where a test currently asserts
a full URL including optional query text.

Run this zero-literal audit before moving on:

```bash
git grep -n 'http://localhost:5173' -- tests/e2e
```

Expected: no results. Do not replace broad `**/api/...` fixture patterns in
unrelated specs; they are not part of the literal-origin defect.

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

Expected: the non-default-port invocation executes and all migrated affected
specs pass. Record the port-owner check after each command and classify any
startup failure separately from an assertion failure.

- [ ] **Step 5: Commit the portable-origin increment**

```bash
git add \
  frontend/mission-planner/tests/e2e/api-origin.spec.ts \
  frontend/mission-planner/tests/e2e/leg-detail-responsive.spec.ts \
  frontend/mission-planner/tests/e2e/mission-workflow.spec.ts
git commit -m "test(e2e): honor configured fixture origin"
```
