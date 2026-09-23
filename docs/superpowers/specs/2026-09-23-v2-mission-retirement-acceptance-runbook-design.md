# V2 Mission Retirement Acceptance Runbook Design

**Issue:** #178

## Purpose

Provide a repository-owned, deterministic acceptance runner for the V2 mission
retirement candidate. It must turn the existing ad-hoc exact-SHA runtime and
headed-browser acceptance process into a bounded, reproducible command with
durable evidence and safe cleanup.

The runner must make the next full acceptance run operationally reliable while
also separating inexpensive iteration checks from the one expensive final image
proof. A no-cache Docker build is final-candidate evidence, not the default cost
of every edit.

## Scope

The delivery adds acceptance infrastructure only. It must not change production
application routes, V2 lifecycle behavior, deployment defaults, Portainer/GHCR
configuration, CI publishing, credentials, or live deployment.

The runner owns a task-scoped detached exact-SHA checkout, temporary Compose
configuration, loopback ports, task browser/display resources, and an evidence
root outside tracked repository content. It preserves pre-existing canonical
worktree reports and task-created named volumes.

The implementation is a thin documented shell entry point over focused Python
stdlib modules. Python owns configuration validation, command construction,
subprocess results, BuildKit reconciliation, artifact manifest construction,
and cleanup decisions. Shell remains an operator-facing launcher, not the
source of complex pipeline/error semantics.

## Interfaces and Inputs

The runner accepts and validates:

- a full 40-character candidate SHA and named feature ref;
- an evidence root;
- a unique Compose project name and explicit unique loopback ports;
- the required pinned Chrome executable;
- a task CDP port and mode-0700 browser profile path;
- a task-owned virtual display identity;
- an optional explicit phase; and
- `full` as the default phase.

Invalid, abbreviated, mismatched, or unresolved SHA/ref inputs fail before a
worktree, Docker resource, or browser process is created. Inputs and selected
phase are recorded in the manifest without secrets.

The browser executable is:

```text
/home/brian/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome
```

The runner labels its browser evidence **headed Chrome on a task-owned virtual
display**. It must never label it as physical-display evidence.

## Staged Execution Model

The runner supports explicit phases so routine iteration does not repeatedly
consume the final-build budget. Each phase emits its own retained result and
cannot report a stronger outcome than it exercises.

### `preflight`

This phase has no Docker or browser work. It records independently bounded
steps:

1. local identity within 15 seconds;
2. named remote-ref check within 30 seconds, with one narrow retry at most;
3. detached exact-SHA checkout creation or verification within 45 seconds; and
4. sanitized Compose topology resolution within 45 seconds.

The runner never fetches all refs, broad-scans the repository/cache, or combines
identity, topology, and build in one command. Topology uses only tracked
`.env.example` data plus a task-owned external override. It never reads or
copies a private `.env` file.

### `static`

This is the routine source/test validation phase. It creates a task virtual
environment using `uv` and both declared backend manifests:

```text
backend/starlink-location/requirements.txt
backend/starlink-location/requirements-dev.txt
```

It records Black and Ruff versions, then runs from
`backend/starlink-location` exactly:

```text
black --check app tests
ruff check app tests
pytest -q
```

It also performs the frontend clean install, lint, unit tests, browser
discovery, and configured full Chromium suite. It does not run a separate
frontend production build before configured Playwright, because the Playwright
web server already builds before serving preview.

`static` never invokes Docker, Compose, Xvfb, or Chrome directly. Its manifest
classification is static/browser-suite evidence only, not deployed runtime or
headed-CDP acceptance.

### `browser-card`

This cheap preflight launches only task-owned Xvfb and the pinned headed Chrome
against a neutral local page. It records display identity/geometry, Xvfb PID
and stderr, Chrome path/version/SHA, process group, profile, CDP port, stdout,
stderr, readiness probes, CDP calls, metrics, and a neutral PNG.

It polls child state and `/json/version` for up to 120 seconds. It imports
Playwright only through `@playwright/test`. It does not use `Emulation.*`
metrics or screen overrides.

Before product navigation, it calls `Browser.getWindowForTarget`, then
`Browser.setContentsSize(1920,1080)`, retaining both calls/results and
`Browser.getWindowBounds`. It requires:

- `innerWidth=1920`;
- `innerHeight=1080`;
- visual viewport exactly `1920×1080`;
- device pixel ratio `1`; and
- decoded neutral PNG exactly `1920×1080`.

A mismatch stops before product navigation and is a browser-environment
coverage gap, not a reason to churn launch flags. The card is rerun whenever
its code, Chrome version/path, display server, or CDP protocol contract changes.

### `runtime-cached`

This explicitly non-final diagnostic phase may use a valid task-owned image tag
or Docker layer cache to investigate the backend, Nginx proxy, or real journey
without repeated cold builds. It still uses unique resources, evidence, and
cleanup, but its manifest states that it is cached diagnostic evidence and
cannot claim final exact-SHA production acceptance.

It never reuses containers, browser profiles, ports, volumes, or images as
final acceptance evidence from another task/run.

### `full`

`full` is the default and the only final-acceptance phase. It runs the
preflight, static, and neutral-browser-card stages, then performs one isolated
no-cache build and one deployed browser journey. A new source commit produces a
new candidate SHA and invalidates previous `full` evidence; while iterating on
that candidate, lower-cost applicable phases run first. One fresh full lane is
reserved for the immutable candidate selected for acceptance.

## Isolated Build and Runtime

The root Compose file is not directly safe for acceptance: it has fixed
container names, fixed host ports, persistent volumes, a private `.env`
dependency, and `restart: unless-stopped`. The runner generates an external
task override that replaces inherited ports/container names and routes all
mutable application data to task-owned locations.

The final runtime starts only the two services required by the specified
acceptance contract:

- `starlink-location`; and
- Nginx-served `mission-planner`.

Prometheus and Grafana are not started merely because they are present in the
root topology; they are not required by the stated controls or journey. This
reduces startup time without weakening the scoped contract.

The runner performs exactly one explicit final build:

```text
COMPOSE_BAKE=false docker compose ... build --no-cache --progress=plain
```

It uses a process owner capable of a declared 900-second-or-greater wait. It
records wall time, per-stage timing, plain BuildKit output, named tags, image
IDs, and digests. It never runs `up --build`, begins a concurrent build, or
starts a second no-cache build after the declared budget is consumed.

When the controlling wrapper reports nonzero or timeout, the runner reconciles
rather than blindly rebuilding. For each required candidate service it requires
completed `exporting`, `naming`, `unpacking`, and final `DONE` evidence in the
BuildKit log, then inspects the named tag and image ID. If all expected images
exist and match, it records the wrapper anomaly and proceeds exactly once. A
genuine incomplete/failed build blocks startup and browser work.

After a usable build, it starts exactly once:

```text
docker compose ... up -d --no-build --wait --wait-timeout 180
```

Build elapsed, startup elapsed, and application-ready elapsed are separate
metrics. The runner records task project labels, resolved ports, and image IDs
before controls. It proves:

```text
backend /health             -> 200
frontend                    -> 200
/api/missions               -> 404
/api/missions/test          -> 404
/api/v2/missions            -> 200
```

## Real Deployed Journey

After the neutral browser card and runtime controls pass, the runner uses the
Nginx-served frontend and real backend only. It must not seed state through an
API, intercept/reroute Playwright requests, or navigate directly to hidden
pre-created product state as positive deployed proof.

The journey is:

1. Create New Mission;
2. open the resulting mission detail;
3. Add Leg;
4. upload `docs/missions/acceptance-assets/v2-activation-route.kml`;
5. Activate; and
6. open Overview.

The runner requires browser-observed activation status 200 and, after settle,
visible active V2 route/context/POIs. It retains final metrics and a decoded
final PNG under the same exact-viewport rules as the neutral card, plus bounded
screenshots, accessible/DOM contracts, console evidence, and browser-network
evidence. Existing route-fulfilled Playwright tests remain regression coverage;
they are not substitutes for this production Nginx-to-backend journey.

## Evidence, Failure Classification, and Cleanup

The evidence root is SHA-qualified and task-owned. Directories are mode `0700`
and files are mode `0600`. The manifest binds full SHA/ref, commands/results,
timestamps, phase classification, browser/version provenance, image IDs,
runbook version/checksum, artifact sizes/checksums, and cleanup outcome.

The runner has one `finally` cleanup path. It closes CDP, terminates only
owned browser/Xvfb process groups, removes only owned profile/display files,
and removes task Compose containers/networks while preserving volumes. It then
proves declared ports and owned processes are absent. It checks retained
artifacts and verifies checksums after cleanup. Cleanup failure cannot overwrite
the primary failure; both outcomes are recorded.

Every phase classifies its result as one of: passed at that phase's stated
strength, failed, infrastructure blocker, or coverage gap. `runtime-cached`
and `static` cannot produce a final acceptance pass. A failed acceptance run is
still fully cleaned and retained as evidence.

## Testing

Tests are deterministic and do not use Docker or Chromium as substitutes for
real acceptance evidence. They cover:

1. CLI configuration validation, full-SHA/ref matching, phase selection, and
   command construction;
2. phase isolation: `static` and `browser-card` cannot invoke Docker, while
   `runtime-cached` cannot emit final-acceptance classification;
3. external override construction and resolved-topology checks proving no
   inherited fixed host mappings/container names/private `.env` dependency;
4. BuildKit reconciliation, especially a wrapper nonzero result with both
   required tagged images completed, exported, named, unpacked, and inspected;
5. genuine build failure returning nonzero, skipping Compose startup and browser
   work, and preserving that primary status through cleanup;
6. one-build-only enforcement and no-build startup construction;
7. artifact path containment, permissions, manifest ordering, SHA binding,
   allowed artifact budget, checksum generation, and post-cleanup verification;
8. browser-card protocol construction and neutral local execution before the
   expensive full build; and
9. V2 documentation-contract coverage so instructions cannot silently point to
   a legacy activation route.

A PATH-injected fake Docker executable may validate command sequencing and
failure propagation. It is not runtime acceptance evidence. The completed
`full` phase is the one real Docker/production-browser acceptance run.

## Documentation Impact

Add concise operator documentation under `docs/missions/` and link it from the
mission documentation index. It must state the exact command and inputs,
phase budgets, evidence root/manifest contents, cleanup behavior, final versus
diagnostic classifications, final journey, and no-cache build policy.

It must explicitly explain that cached diagnostics streamline iteration but do
not replace the final exact-SHA fresh image proof. Screenshots, logs, reports,
and other generated evidence remain outside tracked repository content.

## Non-Goals

- Modifying V2 lifecycle or application route behavior.
- Running the root Compose stack or touching another project’s Docker resources.
- Reading private `.env` files or using credentials/live Starlink hardware.
- Building or starting Prometheus/Grafana for this scoped backend/frontend lane.
- Treating Playwright fixtures, API seeding, or direct state navigation as
  deployed-journey proof.
- Replacing the required final no-cache exact-SHA image build with cache-only
  controls.
- Committing generated acceptance evidence to the repository.
