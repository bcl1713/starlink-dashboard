# Frontend dependency audit and remediation

Issue [209](https://github.com/bcl1713/starlink-dashboard/issues/209), audited
2026-10-03. Targeted updates remove all findings reported by the current npm
audit: 28 affected packages in the full tree and five in the production
dependency tree now both report zero. No advisories are deliberately deferred.
The full browser suite retains three failures reproduced on the unchanged
baseline; this report does not claim a green browser gate.

## Audited snapshot

The baseline is `dev` commit `b9b7617d` after the Overview traffic changes.
Dependency implementation commit: `a1a3d05ff75bd9a20e74e2bf918902180ac559a2`.
Later documentation changes do not alter that product source or lockfile. The
audit used Node 22.12.0 and npm 10.9.0.

| Dependency tree                           | Before                                 | After |
| ----------------------------------------- | -------------------------------------- | ----- |
| All dependencies                          | 1 critical, 22 high, 4 moderate, 1 low | 0     |
| Production dependencies with `--omit=dev` | 4 high, 1 moderate                     | 0     |

These are counts of affected packages, including dependent packages reported
through vulnerable children. The baseline contains 87 unique advisory URLs; they
are retained with identifiers, ranges, dependency edges and installed paths in
the
[full baseline audit](evidence/2026-10-03-frontend-dependency-audit/audit-before.json).
The
[production baseline](evidence/2026-10-03-frontend-dependency-audit/audit-prod-before.json),
[full final audit](evidence/2026-10-03-frontend-dependency-audit/audit-after.json)
and
[production final audit](evidence/2026-10-03-frontend-dependency-audit/audit-prod-after.json)
record the corresponding snapshots. A clean audit describes this registry
snapshot; it does not establish that every possible vulnerability is absent.

## Targeted updates

| Direct dependency                | Before | After  |
| -------------------------------- | ------ | ------ |
| axios                            | 1.13.2 | 1.20.0 |
| react-router-dom                 | 7.9.6  | 7.18.4 |
| postcss                          | 8.5.6  | 8.5.28 |
| vite                             | 7.2.4  | 7.3.6  |
| vitest                           | 4.0.13 | 4.1.11 |
| typescript-eslint                | 8.47.0 | 8.48.0 |
| @typescript-eslint/parser        | 8.47.0 | 8.48.0 |
| @typescript-eslint/eslint-plugin | 8.47.0 | 8.48.0 |

Manifest minimums advance to these patched releases within existing major
versions. The TypeScript ESLint packages remain aligned. Their 8.48.0 release
avoids the newer Node requirement introduced through the latest visitor keys.
After updating the direct dependencies, the remaining flagged Babel, humanfs,
Ajv, brace-expansion, flatted, js-yaml, minimatch, picomatch and Rollup packages
were refreshed within their parents' declared ranges. No overrides, forced
upgrades or blanket `npm audit fix` were used. The
[version inventory](evidence/2026-10-03-frontend-dependency-audit/lock-version-changes.json)
records transitive changes, including platform-specific optional packages.

npm's ordinary update first crashed in Arborist peer resolution and an explicit
install subsequently rejected the old TypeScript ESLint peer set. Lockfile
generation used `--legacy-peer-deps`, which the repository already uses in CI.
The final lockfile then passed a fresh **plain `npm ci`**, and the unchanged
production frontend Dockerfile also completed its plain `npm ci` step. Product
installation commands and CI configuration are unchanged.

## Exposure assessment

| Package family                          | Use in this project                           | Assessment                                                                                                                                                      |
| --------------------------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Axios and its HTTP helpers              | Same-origin browser API client                | Browser request handling is exercised; Node HTTP proxy, redirect and stream advisories describe APIs absent from the browser runtime.                           |
| React Router                            | Declarative `BrowserRouter` client navigation | Browser redirect advisories warrant updates; framework server actions, SSR, RSC and the `__manifest` server endpoint are not configured.                        |
| Vitest and mocker                       | Development test runner                       | The critical advisory concerns a listening Vitest UI server. The tracked `vitest run` command does not start it; both critical and mocker findings are patched. |
| Vite, Babel, PostCSS and Rollup         | Development server and build tooling          | File access and build-time advisories concern development/build inputs or exposed development servers. Production serves compiled assets through Nginx.         |
| ESLint, globbing, YAML, Ajv and humanfs | Development lint/build dependency paths       | Findings concern tooling inputs and filesystem operations, rather than a deployed Node server in the frontend image.                                            |

This classification follows the checked-in application and Dockerfiles, not
severity alone. npm's production dependency classification is broader than the
JavaScript actually shipped to browsers. Maintainer descriptions establish the
[Vitest UI condition](https://github.com/vitest-dev/vitest/security/advisories/GHSA-5xrq-8626-4rwp)
and the
[Vite Windows development-server condition](https://github.com/vitejs/vite/security/advisories/GHSA-fx2h-pf6j-xcff).
The
[React Router maintainer advisory](https://github.com/remix-run/react-router/security/advisories/GHSA-chx6-hx7r-mcp5)
describes framework manifest handling. Other advisory-specific conditions and
fixed ranges are preserved in the audit inventory. This audit found affected
versions; it did not demonstrate exploitation of this installation.

## Verification

Before the update, all 613 frontend unit tests, ESLint and the production build
passed. After a clean installation, all 613 tests in 80 files and ESLint pass
again. Both final audit commands exit zero. The production frontend image builds
without cache using its unchanged Dockerfile and the dependency commit above.

The full Chromium inventory ran serially against the production preview with the
existing assertions and no retries: **118 passed, three failed and one did not
run**, in 21.7 minutes. The three failures are:

- `overview-globe.spec.ts:960`: the retained-stars and next-POI/landing
  screenshot differs from its stored reference by about 4% of pixels.
- `overview-metric-history-fullscreen.spec.ts:56`: the compact metrics/legend
  geometry assertion fails at a 640px viewport height.
- `overview-metric-history.spec.ts:107`, display scale 2: the retained sample
  jumps left beyond the existing motion tolerance after a delayed poll.

An independent temporary checkout of the exact baseline source and original
lockfile, installed with plain `npm ci`, reproduces **all three failures** under
the same Chromium 153.0.8010.12, serial settings and unchanged assertions. The
640px geometry values match exactly between baseline and candidate. This
establishes that these observations predate the dependency update; it does not
establish their root causes or whether their frequency changed. The motion
observation is consistent with the deferred investigation in issue 234. No
snapshot was refreshed and no assertion or tolerance was relaxed.

The serial globe group skipped its persisted custom-history-window case after
the screenshot failure. Running that case independently passes (1/1). The first
failed attempt is retained in `/tmp/starlink-209-e2e.log` and its three failure
artifact directories in `/tmp/starlink-209-e2e-first-run/`. Baseline comparison
output is `/tmp/starlink-209-baseline-browser.log`; traces remain in the
temporary baseline checkout. The skipped-case result is
`/tmp/starlink-209-skipped-browser.log`. Fixture browser results are distinct
from the isolated production Nginx/backend path.

The production simulation project `starlink-issue209` uses the actor's
configured `unix:///run/user/1002/docker.sock`, isolated named volumes and
loopback ports 18209 for Nginx, 18210 for the backend and 18211 for Prometheus.
Real Nginx requests return 200 for status, missions, routes, Overview history
and settings; the backend health is 200 and the Prometheus scrape target is UP.
Two initial diagnostic requests used incorrect history paths and returned 404;
the recorded requests to the documented `overview-history` paths succeed.

The real production browser smoke passes root redirect and collection loading,
mission creation with detail navigation and persisted reload, Configuration
history-window saves and reload, the rendered globe and five panels with native
fullscreen, and CSV export. The successful probe records 38 API responses and
zero page errors. Desktop and fullscreen screenshots were inspected. Response,
image and dependency identities are recorded in
`/tmp/starlink-209-production-runtime.json`,
`/tmp/starlink-209-production-smoke.json` and
`/tmp/starlink-209-production-browser-rerun/manifest.json`. The
[verification summary](evidence/2026-10-03-frontend-dependency-audit/verification-summary.json),
[production image identities](evidence/2026-10-03-frontend-dependency-audit/production-runtime.json),
[initial browser probe](evidence/2026-10-03-frontend-dependency-audit/production-browser-first.json)
and
[corrected browser probe](evidence/2026-10-03-frontend-dependency-audit/production-browser-final.json)
are retained permanently with this report. The
[desktop screenshot](../assets/issue-209-overview-desktop.png) and
[fullscreen screenshot](../assets/issue-209-overview-fullscreen.png) preserve
the rendered production result.

The initial production probe completed all five workflows but failed its final
blanket HTTP-error assertion because GPS configuration intentionally returns 503
in simulation mode. The backend's checked-in contract and actual response agree.
The corrected probe asserts that exact status and detail while continuing to
reject other HTTP errors. The initial failed probe, screenshot and manifest
remain in `/tmp/starlink-209-production-browser/`; the corrected result is
separate. All mission/settings changes used only this task's isolated volumes.

Independent review found no critical or important implementation issues.
Manifest and lockfile dependency maps agree, all required transitive ranges are
satisfied, and registry downloads retain integrity metadata. New bundled
Tailwind records inherit their unchanged parent tarball's integrity.

## Remaining verification limits

The unchanged jsdom family still emits five Node engine warnings on the pinned
Node 22.12.0 runtime: jsdom, undici, whatwg-url and two @asamuzakjp packages.
Their versions and engine requirements are identical to the baseline. A new
optional Rollup cross-build package, `@napi-rs/lzma-linux-x64-gnu`, requires a
higher Node version; it is optional development tooling and is not loaded by
Rollup's native runtime loader. Clean install, tests and production build
succeed on the current runtime. Aligning the broader Node support policy is
separate maintenance, consistent with the warning inventory in issue 226.

The production build retains its existing large-chunk warning. This dependency
change makes no bundle-splitting or toolchain policy changes. Windows, other CPU
architectures, Firefox and Safari are not verified in this Linux Chromium run.
No production rollout or merge is part of this verification. The full browser
gate remains failing despite the reproduced baseline failures; this dependency
delivery does not waive that gate.

## Reproduction

From `frontend/mission-planner`:

```sh
npm ci
npm audit --json
npm audit --omit=dev --json
npm run test:unit
npm run lint
npx playwright test --list --project=chromium
npx playwright test --project=chromium --reporter=line
```

Playwright owns its production build through the existing server configuration.
Raw session logs and production response/rendering evidence are retained at
`/tmp/starlink-209-*` and copied into the ignored workspace directory
`.superpowers/sdd/issue-209-a1a3d05f/`, including the original candidate and
baseline failure traces and videos. That workspace directory is not part of the
Git branch. The dated audit JSON, verification manifests, version inventory and
production screenshots above accompany this report in Git.
