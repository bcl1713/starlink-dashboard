# V2 Acceptance Browser Recovery Design

## Purpose

Restore trustworthy exact-head V2 final acceptance by eliminating two verified harness failures:

1. a final lane can be supplied a headless browser that does not satisfy the 1920×1080 native viewport contract certified by platform health; and
2. an adapter error can leave the Node CDP connection alive, masking the actual error as a generic runner timeout.

This is acceptance-platform remediation, not a product feature change. The V2 product journey remains the authority for the user-visible create → leg → KML upload → activate → Overview flow.

## Evidence motivating the change

At `8105e2dd646e3b3cc2c72c9dea6dc056170a328b`, health and static acceptance passed. The monitored final lane built usable images but reported `product journey adapter timed out`.

A no-build diagnostic against those sealed images reproduced the underlying adapter error before any product interaction:

```text
Error: screenshot is not a decoded PNG
  at pngDimensions (.../v2-mission-retirement.mjs:52)
  at viewportArtifact (.../v2-mission-retirement.mjs:92)
  at runV2MissionRetirement (.../v2-mission-retirement.mjs:206)
```

The final wrapper had launched headless Chromium, while the health card had certified a headed Xvfb/CDP browser at 1920×1080. The adapter catch handler set `process.exitCode` but its `connectOverCDP()` connection remained open; the child therefore outlived the error and the runner’s 180-second limit replaced the useful error with a timeout.

## Architecture

### Platform-owned final browser session

The acceptance platform owns the final browser lifecycle. The runner must derive the session from the administrator-provisioned profile and start the same browser/display topology used by the neutral health card:

- profile-pinned executable only;
- headed Chromium under task-owned Xvfb;
- loopback CDP endpoint with a unique task-owned port and profile directory;
- native viewport/raster validation at 1920×1080, DPR 1, before product navigation;
- durable bounded browser/Xvfb logs; and
- one `finally` cleanup owner for browser, display, profile, and task-owned runtime resources.

Product contracts and CLI callers must not choose headless flags, browser executable paths, CDP ports, display configuration, or cleanup logic. `--browser-session` and `--deployed-origin` remain valid only as explicitly provisioned platform inputs for controlled tests; production final acceptance obtains them through platform authority.

### Adapter failure contract

The V2 adapter must cleanly dispose of its CDP connection in all outcomes. The exported journey function continues to throw the original error. The CLI entry point must explicitly disconnect/close its Playwright attachment before process exit, then return a non-zero result promptly with the original stack on stderr.

The adapter must not convert a precise viewport or semantic error into a timeout. It must preserve the primary error while still detaching the lifecycle CDP session.

### Bounded diagnostics and classification

The runner retains redacted, byte-bounded adapter stdout and stderr on both non-zero exit and deadline expiry. Its failure message distinguishes:

- adapter non-zero exit with preserved stderr;
- adapter deadline expiry with bounded partial output; and
- browser platform preflight failure before any no-cache build.

The runner may not report a final pass unless the final browser session has the same certified native viewport/raster identity required by health.

### Acceptance flow

1. Exact-head health certifies the external profile and the neutral native browser/display card.
2. Static runs only after health succeeds.
3. Final creates one task-owned browser session using the platform lifecycle, proves its neutral viewport, then performs the sole no-cache build, no-build startup, controls, and V2 journey.
4. A final build ledger is claimed before the build. A foreground command timeout is avoided by running the final runner as a monitored 900-second process with durable logs.
5. Final evidence seals browser lifecycle diagnostics, image IDs, controls, journey artifacts, and cleanup verification.

## Testing and verification

Regression tests must cover:

- a V2 adapter failure after CDP attachment exits within the runner’s process bound and preserves the original error;
- final browser provisioning uses the health-compatible headed/Xvfb platform authority, not caller-supplied headless behavior;
- a mismatched viewport is rejected before the final no-cache build;
- runner manifests retain bounded adapter diagnostics and classify exit versus timeout accurately;
- cleanup removes task browser/display resources, task runtime resources, listeners, task root, and browser profile while retaining evidence and volumes;
- existing platform, contract, adapter, and documentation tests remain green.

Documentation impact: update the acceptance-platform operator documentation with the final browser ownership model, monitored 900-second execution, bounded diagnostic locations, and recovery rule: after an interrupted final claim, inspect the ledger/images/resources and obtain explicit authorization before a new final attempt.

## Non-goals

- No product UI, mission behavior, KML semantics, or backend business logic changes.
- No change to the V2 product-only contract to expose platform operational controls.
- No headless/emulated viewport substitution for native 1920×1080 evidence.
- No automatic final retries or deletion of an existing final build claim without explicit human authorization and reconciliation.

## Success criteria

A final acceptance run at a newly published exact SHA:

- uses the profile-pinned headed/Xvfb browser and proves native 1920×1080/DPR-1 viewport/raster before journey actions;
- reports the actual adapter error promptly when the journey fails;
- does not leave CDP, Chrome, Xvfb, task Compose resources, listeners, profiles, or task roots behind;
- retains and verifies sealed evidence; and
- produces a final pass only after the full V2 user-visible journey succeeds through the production runtime path.
