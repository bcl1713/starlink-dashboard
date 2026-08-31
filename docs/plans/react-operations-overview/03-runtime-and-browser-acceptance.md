# Phase 3: React Operations Overview Runtime and Browser Acceptance

> **For Hermes:** Start after Phase 2. Evidence is valid only for the exact
> clean PR-head SHA under test; rerun affected gates after any commit.

This phase proves temporal continuity, every accepted viewport, real dual-run
parity, runtime cleanup, and the security/CSP boundary. Use the
[responsive acceptance matrix](02-dashboard-ui.md#responsive-acceptance-details)
and the
[master exact-head rule](../2026-08-29-react-operations-overview.md#binding-baseline-and-exact-head-rule).

## Browser and runtime tasks

### Task 13: Add browser acceptance and temporal evidence

**Files:**

- Modify: `frontend/mission-planner/package.json`
- Modify: `frontend/mission-planner/package-lock.json`
- Create/modify: `frontend/mission-planner/tests/e2e/overview.spec.ts`
- Create/modify:
  `frontend/mission-planner/tests/e2e/overview-continuity.spec.ts`
- Modify: `frontend/mission-planner/tests/e2e/api-origin.spec.ts`
- Modify: `frontend/mission-planner/tests/e2e/fixtures/overview.ts`

**Steps:**

1. Route API/tile responses to deterministic fixtures. Assert all eleven panel
   concepts, twelve map layers, controls, states, accessible names, same-origin
   requests, no console/page errors, and no failed first-party requests.
2. At both `1280x800` desktop and `390x844` mobile, select each POI option in
   exact order and assert state ownership, accessible name/value, responsive
   disclosure, persistence across reload/refresh, and the request URL. Prove All
   POIs sends no `category` parameter and every other value has exact encoding.
3. Parameterize `1920x1080`, `1280x800`, `1024x768`, `768x1024`, `390x844`, and
   `320x568`. At each, assert no root horizontal overflow and capture named
   full-page/initial screenshots. Prove the size-specific hierarchy, map height,
   disclosure parity, UTC visibility, touch behavior, and no scroll trap.
4. Add `@axe-core/playwright` as a dev dependency with
   `npm install --save-dev @axe-core/playwright`, changing both package files.
   Run `npx playwright test tests/e2e/overview.spec.ts --grep @axe`; zero
   serious or critical violations are allowed. Retain manual keyboard-only,
   screen-reader smoke, WCAG 2.2 AA contrast, reduced-motion, and 44x44 target
   evidence.
5. For fullscreen, capture screenshots and assert overflow/layout before entry,
   during native fullscreen, during kiosk fallback after a forced API rejection,
   and after exit. Prove filter/layer/map/dashboard state survives every phase,
   focus enters sensibly, and focus returns to the trigger after exit.
6. For continuity, wait until initial data and remote tile activity settle, then
   install browser observers before the first measured request and keep them
   active through at least five scheduled one-second refreshes, one actual
   manual refresh, its completion, and settle. The primary pass/fail oracle is
   event-driven browser/DOM/object-lifecycle observation correlated to request
   start and completion, not a minimum screenshot or video frame rate.
7. Assign every refresh/request an immutable correlation ID and record its
   source, cycle, kind, start, completion/error, and raw monotonic timestamps.
   Record every `MutationObserver` event and test-world object identity
   transition with the active request/cycle IDs. At request start, while
   pending, at completion, and after settle, sample non-empty signatures and
   bounding boxes for the mounted Overview root, Leaflet map/container
   ownership, all twelve layer controls and rendered-feature ownership, three
   chart canvases and series, stable summaries/history disclosures, and
   last-good content. Fail on any transient removal, replacement, zero
   dimension, identity reset, unexpected count regression, focus loss,
   filter/layer/disclosure change, scroll change, raw console/page error, or
   first-party request error. Retain honest supporting screenshot/video evidence
   with its raw timestamps, achieved cadence, and gaps, but impose no minimum
   fps. Undersampling limits visual claims, cannot override an observer failure,
   and must not be disguised by timestamp rewriting, hidden animation, or
   manufactured paint. Keep exact- view screenshots for the accepted viewport
   states.
8. Run nominal, empty, partial/total error, truthful per-source stale/recovery,
   IDL, thresholds, radar/basemap failure, and rotation. Use the same fixture,
   viewport, stable-region contract, and cadence again at final exact head.
9. Add executable no-Grafana tests: static search fails on Grafana URL/port
   3000, `/api/datasources/proxy`, dashboard/plugin assets, or Grafana imports
   in Overview production bundles; with Grafana routes aborted/unavailable,
   React remains functional and browser network asserts no request targets port
   3000, Grafana paths, sessions, plugins, dashboards, or assets.
10. Run:

    ```bash
    cd frontend/mission-planner
    npm run build
    npm run test:unit
    npx playwright test tests/e2e/overview.spec.ts \
      tests/e2e/overview-continuity.spec.ts tests/e2e/api-origin.spec.ts
    ```

    Expected: all scenarios pass; traces, screencast cadence report, and
    screenshots identify exact HEAD.

11. Commit: `test: add operations overview browser acceptance`.

### Task 14: Prove an exact-head isolated real stack

**Files:** no feature files. A defect returns to its owning TDD task/commit,
then this entire exact-head task reruns. Runtime manifests/evidence stay outside
Git.

**Steps:**

1. Require `git status --porcelain` empty; set immutable
   `SHA=$(git rev-parse HEAD)`, `PROJECT=react-overview-${SHA:0:12}`, and
   `EVIDENCE=/home/brian/starlink-dashboard-react-overview-evidence/$SHA/task-14`.
   Create that mode-0700 directory. No evidence-producing commit may follow this
   run; if HEAD changes, use a new SHA-qualified directory and rerun.
2. Create `$EVIDENCE/runtime.env` only from `.env.example` plus explicit
   non-secret simulation values; never read/reuse `.env` or credentials. Set
   unique test credentials and fixed candidate host ports `18000`, `19090`,
   `13000`, and `15173`; preflight with `ss` and Docker inspection and abort if
   any port/name is occupied. Do not stop or alter the occupying resource.
3. Render
   `docker compose --env-file "$EVIDENCE/runtime.env" config --format json` to
   evidence, then generate `$EVIDENCE/compose.isolated.yml` with a checked
   Python transform. It must remove every `env_file`, replace all fixed
   `container_name` values with `${PROJECT}-<service>`, replace host ports with
   the four preflighted ports, use `${PROJECT}-<volume>` and `${PROJECT}-net`,
   preserve bind mounts as absolute repository paths/read-only where possible,
   and use task-owned disposable state volumes. Validate the generated model
   rejects unqualified names, normal ports, external volumes/networks, and build
   contexts outside this exact worktree. `docker compose -p` alone is forbidden.
4. Build backend and Mission Planner from the clean exact worktree without cache
   into SHA-qualified image tags and apply OCI labels
   `org.opencontainers.image.revision=$SHA` and
   `org.opencontainers.image.source=<repository URL>`. Pull pinned Compose base
   images, record source refs/digests, `docker image inspect` IDs/RepoDigests/
   labels, and generated Compose digest before startup. The isolated manifest
   references only those recorded image IDs/tags; it does not rebuild at `up`.
5. Start only with
   `docker compose -p "$PROJECT" -f "$EVIDENCE/compose.isolated.yml" up -d --no-build`.
   Record project name, SHA, Compose labels, container IDs, configured/running
   image IDs, ports, networks, volume names, endpoints, `docker compose ps`, and
   health results. Assert each running image ID equals its recorded built/pulled
   image and each container has the task project label; provenance mismatch
   fails.
6. Run real Chromium against `http://127.0.0.1:15173/overview` at all six exact
   viewports. Retain screenshots, traces, HAR, console/page errors, panel/layer/
   state checks, POI filters, responsive hierarchy, axe/manual accessibility,
   fullscreen four-phase evidence, and Nginx response headers. Prove the exact
   CSP on the Nginx-served SPA and `nosniff`/same-origin/no-redirect tile
   behavior, not merely direct FastAPI or mocked-preview behavior.
7. Repeat the event-driven settled continuity test across five scheduled plus
   one actual manual refresh on this real runtime, with observers active before
   the first measured request through manual completion/settle and with stable
   regions/object identity correlated to request and console evidence. Retain
   honestly timestamped supporting captures at the achieved host cadence, with
   no minimum-fps pass criterion. Run React/Grafana parity over the same
   30-minute simulation window, IDL, interruption/recovery, outage,
   bounded-memory/network soak, and disposition every delta. Then stop only
   `${PROJECT}-grafana`, prove React remains functional, and assert HAR contains
   no Grafana/3000 request.
8. Run exact-head gates and store logs under `$EVIDENCE/commands/`:

   ```bash
   git status --porcelain && test "$(git rev-parse HEAD)" = "$SHA"
   python -m pytest tools/tests/test_fullscreen_overview_dashboard.py -q
   python -m pytest tools/tests/test_mission_planner_nginx.py -q
   (cd backend/starlink-location && python -m pytest -q)
   (cd frontend/mission-planner && npm run lint && npm run build && npm run test:unit)
   (cd frontend/mission-planner && npx playwright test)
   pre-commit run --all-files
   git diff --check
   ```

9. Before teardown, copy Compose logs, inspect JSON, health responses, manifest,
   its SHA-256, screenshots/traces/HAR, accessibility notes, parity table, and
   cadence report into `$EVIDENCE`; create and verify `SHA256SUMS`. Record every
   retained absolute path in `$EVIDENCE/MANIFEST.txt`.
10. In a `trap` that runs after success/failure, run `down --remove-orphans`
    against only the generated manifest/project, without `-v`; preserve all
    pre-existing volumes and resources. Remove only explicitly task-owned
    disposable volumes after evidence retention. Verify by project label/name,
    `docker ps -a`, `docker network ls`, volume inspection, `ss` on four ports,
    and browser-process command lines that no task container, network, port, or
    Playwright/Chromium process remains. Re-run `sha256sum -c` and verify every
    manifest path exists. Cleanup failure fails Task 14.
11. No commit. PR evidence links the SHA-qualified durable directory/artifacts.

## Security, privacy, and CSP acceptance

- Browser traffic remains same-origin `/api/...`; no direct Prometheus, Grafana,
  RainViewer, datasource proxy, or internal Docker hostname.
- Enforce Phase 1 deterministic shape/body/point limits, rate/concurrency/
  cancellation/coalescing, RainViewer host/DNS/path/redirect checks, and safe
  errors. Security tests exercise rejection paths, not prose assurances.
- No public IP in GEP frontend contracts, logs, evidence, tooltips, or
  accessible text. Render display fields as React text; never use
  `dangerouslySetInnerHTML`.
- CSP keeps same-origin radar tiles and the exact ArcGIS HTTPS `img-src`
  allowance. The Nginx/browser CSP implementation adds only `blob:` to `img-src`
  as needed for internal, revoked radar object URLs; it leaves `connect-src`
  unchanged and adds no direct RainViewer browser origin or network access.
  Preserve `object-src 'none'`, `frame-ancestors 'none'`, `form-action 'self'`,
  `base-uri 'self'`, and fullscreen permissions.
- Verify security headers through Mission Planner Nginx on SPA/API/tile
  responses and no CSP console violation at every real-stack acceptance
  viewport.
