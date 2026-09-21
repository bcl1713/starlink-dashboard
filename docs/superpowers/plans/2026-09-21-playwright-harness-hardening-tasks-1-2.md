# Playwright Harness Hardening: Tasks 1-2

## Task 1: Add configured-origin helpers and unit coverage

**Files:**

- Create: `frontend/mission-planner/tests/e2e/support/configured-origin.ts`
- Create: `frontend/mission-planner/src/test/configured-origin.test.ts`

**Interfaces:**

- Consumes: a base URL string from Playwright `testInfo.project.use.baseURL`.
- Produces: `configuredOrigin(baseURL: string | undefined): string`,
  `routeGlob(baseURL: string | undefined, pathname: string): string`, and
  `requestUrlPattern(baseURL: string | undefined, pathname: string): RegExp`.
- `configuredOrigin` returns a normalized URL origin and throws a clear
  test-setup error if the configured base URL is absent or not an absolute
  HTTP(S) URL.
- `routeGlob` returns `<origin><pathname>**` and requires `pathname` to begin
  with `/`.
- `requestUrlPattern` matches `<origin><pathname>` followed by either `?` or end
  of URL; it escapes the origin and pathname before constructing the expression.

- [ ] **Step 1: Write failing helper tests**

```ts
import { describe, expect, it } from "vitest";
import {
  configuredOrigin,
  requestUrlPattern,
  routeGlob,
} from "../../tests/e2e/support/configured-origin";

describe("configured E2E origin helpers", () => {
  it("builds route and request patterns from a supplied non-default port", () => {
    const baseURL = "http://localhost:5187/";

    expect(configuredOrigin(baseURL)).toBe("http://localhost:5187");
    expect(routeGlob(baseURL, "/api/v2/missions")).toBe(
      "http://localhost:5187/api/v2/missions**",
    );
    expect(requestUrlPattern(baseURL, "/api/v2/missions")).toMatch(
      "http://localhost:5187/api/v2/missions?limit=10",
    );
    expect(requestUrlPattern(baseURL, "/api/v2/missions")).toMatch(
      "http://localhost:5187/api/v2/missions",
    );
    expect(routeGlob("http://localhost:5173", "/api/routes")).toBe(
      "http://localhost:5173/api/routes**",
    );
  });

  it("rejects a missing base URL and a relative route path", () => {
    expect(() => configuredOrigin(undefined)).toThrow(/baseURL/i);
    expect(() => routeGlob("http://localhost:5173", "api/routes")).toThrow(
      /pathname/i,
    );
  });
});
```

- [ ] **Step 2: Run the helper test to verify the missing-module RED**

Run from `frontend/mission-planner`:

```bash
npm run test:unit -- src/test/configured-origin.test.ts
```

Expected: FAIL during collection because `configured-origin.ts` does not exist
yet. If the command instead fails because Vitest discovers E2E specs
incorrectly, stop and record that harness boundary failure before changing
helper code.

- [ ] **Step 3: Implement the minimal helper module**

```ts
function requireAbsoluteBaseURL(baseURL: string | undefined): URL {
  if (!baseURL) {
    throw new Error("Playwright project.use.baseURL must be configured");
  }

  const parsed = new URL(baseURL);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("Playwright baseURL must use http or https");
  }
  return parsed;
}

export function configuredOrigin(baseURL: string | undefined): string {
  return requireAbsoluteBaseURL(baseURL).origin;
}

export function routeGlob(
  baseURL: string | undefined,
  pathname: string,
): string {
  if (!pathname.startsWith("/")) {
    throw new Error("Route pathname must begin with /");
  }
  return `${configuredOrigin(baseURL)}${pathname}**`;
}

export function requestUrlPattern(
  baseURL: string | undefined,
  pathname: string,
): RegExp {
  if (!pathname.startsWith("/")) {
    throw new Error("Route pathname must begin with /");
  }
  const escaped = `${configuredOrigin(baseURL)}${pathname}`.replace(
    /[.*+?^${}()|[\]\\]/g,
    "\\$&",
  );
  return new RegExp(`^${escaped}(?:\\?|$)`);
}
```

Use the repository formatter to settle line wrapping and replace the escape
expression only if TypeScript or the regression test proves it malformed.

- [ ] **Step 4: Run focused helper coverage and discovery control**

Run from `frontend/mission-planner`:

```bash
npm run test:unit -- tests/e2e/support/configured-origin.spec.ts
npx playwright test --list --project=chromium
```

Expected: helper test passes; Playwright lists browser specs successfully.
Record collected file names/counts and verify the helper test command actually
collected the new file.

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

- Consumes: the existing `PLAYWRIGHT_PORT` configuration and production-build
  preview command.
- Produces: a numeric `webServer.timeout` selected from owned cold-start
  evidence and a trace mode that retains diagnostics for failed no-retry runs.

- [ ] **Step 1: Capture the cold-start baseline before configuration changes**

From a clean branch worktree, ensure no unrelated process owns the test port,
then run one existing focused browser test:

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

Expected: record whether page execution begins and the elapsed time. If the run
ends with `Timed out waiting 60000ms from config.webServer`, preserve it as the
required bootstrap diagnosis; do not retry it or call it product evidence.

- [ ] **Step 2: Write the failing configuration characterization test**

Create `src/test/playwright-config.test.ts` to load the exported Playwright
config and assert:

```ts
import { describe, expect, it } from "vitest";
import config from "../../playwright.config";

function oneWebServer() {
  if (!config.webServer || Array.isArray(config.webServer)) {
    throw new Error("Expected exactly one Playwright webServer configuration");
  }
  return config.webServer;
}

describe("Playwright harness policy", () => {
  it("uses an explicit startup budget and retains no-retry diagnostics", () => {
    expect(oneWebServer()).toMatchObject({
      timeout: expect.any(Number),
    });
    expect(config.use?.trace).toBe("retain-on-failure");
    expect(config.retries).toBe(0);
  });
});
```

Use the repository's existing TypeScript test conventions. The RED must fail
because `timeout` is absent and the current trace policy is `on-first-retry`.

- [ ] **Step 3: Implement the measured policy**

Set `webServer.timeout` to a documented constant that exceeds the observed
healthy cold baseline with explicit headroom. Set `use.trace` to
`retain-on-failure` while retaining `retries: 0`. Do not change worker
parallelism, project selection, build command, preview command, or port
derivation.

Add a README E2E section that records:

```bash
# From frontend/mission-planner; Playwright performs the production build.
npx playwright test --list --project=chromium
npx playwright test tests/e2e/api-origin.spec.ts --project=chromium --reporter=line
npx playwright test tests/e2e/api-origin.spec.ts --project=chromium --reporter=line
npx playwright test --project=chromium --reporter=line
```

Explain the preflight/focused/affected-spec/final-inventory purposes and state
that no standalone `npm run build` precedes Playwright because
`webServer.command` already builds.

- [ ] **Step 4: Run the configuration control and one focused browser check**

Run from `frontend/mission-planner`:

```bash
npm run test:unit -- src/test/playwright-config.test.ts
npx playwright test tests/e2e/api-origin.spec.ts \
  --project=chromium \
  --grep 'loads an empty mission collection' \
  --reporter=line
```

Expected: configuration characterization passes and the browser command reaches
page execution. Record command, elapsed time, test totals, and whether
`playwright-report/` or trace output exists only after an intentionally failed
diagnostic run; do not fabricate a failing product fixture solely to create an
artifact.

- [ ] **Step 5: Commit the startup and diagnostics increment**

```bash
git add \
  frontend/mission-planner/playwright.config.ts \
  frontend/mission-planner/README.md \
  frontend/mission-planner/src/test/playwright-config.test.ts
git commit -m "test(e2e): harden Playwright bootstrap diagnostics"
```
