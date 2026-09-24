# Generic Acceptance Platform Design

## Purpose

Provide a reusable acceptance platform that makes runtime and browser acceptance
repeatable across development branches without rediscovering Docker, browser,
package-manager, timeout, resource-isolation, or evidence mechanics during the
final candidate run.

The platform owns and certifies the execution environment. A branch supplies
only its product contract: candidate identity, declared product gates, required
services, deterministic product assets, and a real user-visible journey. This
separation prevents a branch from reintroducing a fragile browser path, an
undersized wrapper timeout, a duplicated image build, or an unsafe installer.

The V2 mission-retirement flow is the first product contract. It is not the
platform's identity or API.

## Evidence That Drives This Design

The prior V2 acceptance attempts established the following environmental failure
modes:

- a Docker wrapper exited with status 124 even though both images had completed
  BuildKit export, naming, unpacking, and final completion; cleanup then removed
  usable images before `up --no-build`;
- combined `compose up --build` and a later duplicate no-cache build consumed
  the final-run budget without adding evidence;
- a requested `1920x1080` Chromium window produced a `1920x937` page viewport;
- native Python venv bootstrap lacked `ensurepip`, while a previous worker had
  also used floating formatter/linter versions instead of repository pins;
- a missing Chrome executable and untrusted Playwright/npm provisioning required
  repeated security corrections before the browser card could be considered
  trustworthy; and
- UI tests measured polling and animation timing as if they were static state.

These failures are platform capability failures or product-readiness semantics.
They must not be re-solved through a branch-specific runner on every delivery.

## Scope

This delivery introduces a repository-owned generic acceptance platform, product
contract format, V2 product adapter, health certification, deterministic tests,
and operator documentation. It must not alter production application behavior,
API routes, deployment defaults, Portainer/GHCR configuration, CI publishing,
credentials, or live infrastructure.

Generated evidence, browser profiles, temporary Compose overrides, image build
logs, and certification records remain outside tracked repository content.

The V2-specific acceptance-runbook design at
`docs/superpowers/specs/2026-09-23-v2-mission-retirement-acceptance-runbook-design.md`
is superseded for implementation. Its already-committed pure artifact, Compose,
and browser utilities may be retained only after they conform to the interfaces
below. Its uncommitted V2-specific runner files are not an implementation
baseline and must not be committed unchanged.

## Architecture

### Platform authority

The platform owns these non-product concerns:

- immutable platform profile identity and health-fingerprint issuance;
- Docker and Compose executable capability discovery;
- task-owned resource allocation: Compose project, ports, volumes, browser
  profile, CDP listener, virtual display, temporary overrides, and cleanup;
- measured process supervision and a build-state ledger;
- BuildKit log/tag/image reconciliation;
- evidence creation, permissions, manifests, checksums, and post-cleanup
  verification;
- browser-bundle verification, headed Xvfb/Chrome/CDP launch, and exact-viewport
  neutral proof; and
- deterministic result classification and one cleanup owner.

A product contract cannot set binary paths, package-manager commands, browser
provisioning commands, display/CDP flags, timeout policy, Docker invocation
strategy, evidence paths, cleanup strategy, or retry behavior.

### Product contract

A product contract is a reviewed TOML file under
`tools/acceptance/contracts/`. It declares only product semantics:

- full candidate SHA and named ref;
- repository-declared static command groups and working directories;
- services required for the asserted production path;
- public runtime controls with expected status codes;
- paths to tracked deterministic fixtures/assets; and
- a named product journey adapter and its visible assertions.

The V2 contract declares `starlink-location` and `mission-planner`, its declared
backend/frontend static gates, V2 endpoint controls, the tracked activation KML,
and the Create Mission -> Detail -> Add Leg -> Upload -> Activate -> Overview
journey. It cannot contain browser, Docker, or package-install settings.

### Product journey adapter

A journey adapter is a focused Node module under
`tools/acceptance/journeys/`. It consumes only a platform-provided browser
session, deployed frontend origin, task evidence writer, and validated contract
fixture paths. It returns structured product observations. It cannot launch a
browser, choose a Chrome executable, allocate ports, run Docker, create a
profile, or own cleanup.

Journey readiness must be semantic. For polling it records request/lifecycle
correlation rather than a lifetime request count. For animated geometry it waits
for browser-reported animation settlement rather than arbitrary sleeps. Positive
proof uses the shipped user-visible flow; API seeding, request interception, and
hidden/direct state navigation are diagnostic-only and cannot pass acceptance.

### Certified platform profile

A platform profile is versioned tracked configuration under
`tools/acceptance/platform/`. It fixes the supported operating assumptions,
including Docker/Compose commands, resource-allocation ranges, build supervision
budget, browser bundle identity, Xvfb/CDP launch contract, evidence limits, and
health-check implementation version.

The profile references a pre-provisioned immutable browser bundle. Provisioning
is a separate administrative/platform operation, never part of a branch run. A
valid browser bundle record contains:

- absolute executable path, executable version, revision, byte size, and
  SHA-256;
- package/runtime provenance used to obtain it, if applicable;
- a bundle identifier and creation time; and
- a path rooted in the platform-owned browser store.

The platform must verify this record and executable identity before launch. It
must not execute `npm`, `npx`, a Playwright installer, or any installer resolved
through inherited `PATH` during branch acceptance.

### Health certification

`acceptance-platform health` validates the platform profile before any branch
contract may use it. It performs no branch build and no product journey. It:

1. verifies the browser bundle record and executable hash/version;
2. launches a task-owned Xvfb and pinned headed Chrome on a neutral local page;
3. attaches through CDP only after `/json/version` is valid;
4. uses `Browser.getWindowForTarget` and `Browser.setContentsSize(1920,1080)`;
5. requires page `innerWidth` and `innerHeight`, visual viewport, DPR, and a
   decoded neutral PNG to be exactly `1920x1080`, `1920x1080`, `1`, and
   `1920x1080` respectively;
6. verifies task cleanup of browser, display, profile, and listener; and
7. verifies Docker/Compose capability through safe, non-product controls.

A successful run emits a SHA-256-bound health fingerprint containing platform
profile version/checksum, browser bundle identity, measured browser/display
metrics, Docker/Compose identity, health-card version/checksum, timestamps, and
artifact checksum manifest. It is stored outside the repository in a restrictive
platform evidence root.

Branch acceptance requires a current passing fingerprint for the exact platform
profile. A stale, absent, mismatched, or failed fingerprint is an environment
capability failure and blocks before static setup, Docker build, or product
journey. It is never a product regression.

## Acceptance Execution

### Static lane

The platform runs only the contract's repository-declared commands. It provides
known bootstrap profiles rather than accepting branch-specified package-manager
commands. For V2, the Python bootstrap uses `uv` with both repository manifests
and records the resolved Black/Ruff versions before executing exactly:

```text
black --check app tests
ruff check app tests
pytest -q
```

Frontend commands use the declared working directory and the project lockfile.
A standalone build is not run immediately before a Playwright command whose own
configured web server performs that build.

Static results are source/test evidence only; they cannot claim runtime or
browser acceptance.

### Final runtime lane

Only the immutable candidate selected for acceptance may perform the required
fresh image build. The platform owns one build ledger for the tuple:

```text
(platform profile checksum, candidate SHA, contract checksum)
```

It executes exactly one no-cache build with retained plain BuildKit output. A
budget is enforced by a platform-owned supervisor whose effective limit is
recorded and is not lower than the profile's declared budget. It never invokes
`compose up --build`, starts a concurrent build, or retries a no-cache build for
the same ledger tuple.

On a nonzero/timeout result, the platform checks every expected image for
BuildKit `exporting`, `naming`, `unpacking`, and final `DONE` markers, then
inspects the expected tag and image ID. Only when every required image has all
markers and an inspected identity may the result be classified as a wrapper
anomaly and proceed once to no-build startup. Otherwise startup and the journey
are blocked.

The platform creates an external task override from tracked public example
configuration, proves the resolved Compose configuration has no inherited fixed
ports, fixed container names, or private environment file, and starts only the
contract's named services once with `up -d --no-build --wait`. It preserves
volumes and cleans only its own containers and networks.

### Runtime controls and journey

After startup the platform executes the contract's public controls, then gives
the journey adapter the deployed frontend origin. For V2, the controls are the
backend health endpoint, frontend response, retired legacy endpoint responses,
and V2 mission endpoint response. The V2 adapter executes the actual visible
lifecycle and requires browser-observed activation success plus visible active
V2 route/context/POIs after settle.

The platform captures exact viewport metrics and decoded raster evidence both
before product navigation and after the journey. It labels this evidence
**headed Chrome on a task-owned virtual display**. It must never claim physical
monitor evidence.

## Results, Evidence, and Cleanup

The platform uses the following mutually exclusive outcome classes:

- `passed`: the selected contract completed at the stated evidence strength;
- `failed`: a declared product command, control, or assertion failed;
- `environment_blocked`: platform profile or health fingerprint failed before
  product acceptance could begin;
- `coverage_gap`: the environment ran but cannot establish a required contract;
- `diagnostic_only`: an explicitly non-final cached investigation.

A result includes the maximum claim it supports. Only a completed fresh runtime
lane, passing controls, successful real journey, complete exact-viewport proof,
valid checksums, and verified cleanup may assert final acceptance. Every source
commit invalidates final acceptance evidence for its predecessor.

Evidence roots are SHA-qualified and mode-restricted (`0700` directories,
`0600` files). Manifests bind candidate SHA/ref, contract checksum, platform
fingerprint, command results, images, browser identity, journey adapter checksum,
timestamps, classification, and cleanup result. They inventory each retained
artifact by relative path, byte size, and SHA-256. Checksums are verified after
cleanup. Cleanup failure is recorded separately and cannot overwrite a product
failure.

One platform controller owns `finally` cleanup. It closes CDP, terminates only
owned browser/display process groups, removes only owned profile/temporary
files, removes task containers/networks, preserves volumes, and proves its
listeners/processes/resources are absent.

## Testing and Acceptance of the Platform

Deterministic tests must cover:

1. product contracts rejecting operational authority fields and malformed
   candidate/ref/service/control data;
2. health fingerprints rejecting stale profile checksums, browser hash/version
   mismatch, failed neutral viewport metrics, and tampered checksum manifests;
3. browser bundle verification rejecting symlinks, root escapes, substituted
   executables, and untrusted installer/`PATH` authority;
4. build ledger rules: duplicate/parallel build refusal, wrapper-timeout
   reconciliation only with complete markers plus inspected tags, and refusal
   on a missing marker or tag;
5. Compose override/config isolation and resource ownership;
6. result-strength rules that prevent static, cached, or environment-blocked
   outcomes from becoming final acceptance;
7. cleanup preserving the primary outcome and proving owned-resource removal;
8. V2 adapter semantic readiness for polling and animation settling; and
9. manifest path containment, permissions, deterministic ordering, and checksum
   verification after cleanup.

The platform health card itself is real execution evidence. Unit fakes test
construction and failure classification but never replace the health card,
fresh-image run, or deployed-browser journey.

## Documentation Impact

Add platform operator documentation that explains browser-bundle provisioning,
profile health certification, fingerprint inspection, branch-contract authoring,
final-run cost and state machine, result classifications, evidence locations,
and cleanup. Add V2 contract/operator documentation that describes only its
product controls and visible journey.

## Non-Goals

- Replacing mandatory fresh production-path acceptance with cached diagnostics.
- Making branch TOML files responsible for Docker, Chrome, npm, Xvfb, CDP,
  supervision, evidence, or cleanup policy.
- Downloading or provisioning browsers during branch acceptance.
- Reading private environment files, copying credentials, or changing live
  infrastructure.
- Starting unrelated Compose services merely because they appear in a root file.
- Treating API-seeded or intercepted browser state as positive user-journey proof.
- Committing generated logs, screenshots, profiles, health records, or acceptance
  evidence into the repository.
