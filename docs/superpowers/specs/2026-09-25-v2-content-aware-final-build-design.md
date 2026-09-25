# Content-Aware Final Build Supervision Design

## Purpose

Final acceptance must produce a newly attributable image for the exact candidate while avoiding unnecessary dependency installation when dependency manifests have not changed. It must also distinguish a build that continues to make meaningful BuildKit progress from one that has become silent or stalled.

The motivating failure at candidate `45bc7de5afffb0c86272172c60d1546b32b87b0f` reached the frontend `npm run build` stage after downloading images, transferring context, completing `npm ci`, and copying sources, then emitted no further retained BuildKit output before the fixed 1200-second build deadline. It did not reach runtime startup or the browser journey.

## Scope

This change applies only to platform-owned final Compose builds. It does not alter product behavior, browser ownership, WebGL2 certification, startup supervision, control checks, journey semantics, static checks, or persistent volume retention.

Documentation impact is in scope: operator documentation must distinguish the dependency-cache policy, candidate-attributable output rebuild, stall timeout, hard outer deadline, and sealed evidence fields.

## Design

### 1. Dependency cache and candidate attribution

The final build no longer passes Compose's blanket `--no-cache` flag. The existing Dockerfiles already copy dependency manifests before source:

- backend: `requirements.txt` before application files;
- frontend: `package*.json` before application files.

Docker may therefore reuse a dependency layer only when its content-addressed inputs and parent image are unchanged. Any requirements or lockfile change invalidates the relevant dependency layer and reinstalls dependencies naturally.

The platform must force a fresh application/output path for every final candidate by providing a platform-owned, exact candidate-SHA build argument in the rendered task Compose override for every contract service. Each service Dockerfile consumes that argument only after dependency installation and before source-copy/build layers. The candidate SHA invalidates application copy, compile, packaging, and final image layers even when source contents happen to match a previously built candidate.

The platform continues to inspect the resulting service image IDs and binds them to the existing build ledger tuple. The ledger key remains candidate SHA + profile checksum + contract checksum. A usable build is valid only when the rendered topology includes the exact candidate build argument and every inspected service image exists.

The runner must add `--pull` to final Compose build so base-image freshness is checked. It must never accept caller-provided build arguments, cache sources, or Compose flags. `--enable-unsafe-swiftshader` remains prohibited and unrelated browser controls remain unchanged.

### 2. Progress-aware build supervision

The fixed 1200-second internal build timeout is replaced by two independent bounds:

- **Stall window:** 600 seconds without a qualifying BuildKit progress event;
- **Hard outer deadline:** 1800 seconds from Compose build start.

The outer deadline is still finite even if a build continuously emits output. The approved external monitor remains aligned to this 1800-second maximum and must allow runner cleanup to complete after a deadline failure.

A qualifying event must be parsed from bounded, redacted Compose output and be one of:

- a new BuildKit stage identifier or a transition of an existing stage to `DONE`;
- a monotonic byte-count increase within a BuildKit transfer, download, extraction, or export progress record;
- a new command-output line from an active `RUN` stage after the prior qualifying event.

Repeated spinner frames, repeated unchanged byte totals, duplicate stage text, Compose warning lines, and retained-output truncation markers do not reset the stall window.

The executor must stream combined Compose output while the build runs rather than waiting for `communicate()` to return. On stall or hard deadline it terminates Compose, escalates to kill after the existing bounded grace period, retains the redacted bounded output, and returns a classified timeout result.

### 3. Failure classification and sealed evidence

Build failure reasons must distinguish:

- `build_stalled`: qualifying progress ceased for 600 seconds before the outer deadline;
- `build_deadline_exceeded`: progress continued but the 1800-second hard deadline elapsed;
- ordinary nonzero Compose build failures;
- reconciliation or image-inspection failure.

For a stall/deadline failure, the build ledger claim closes as unusable. No no-build startup, service controls, or browser journey may begin.

The final manifest and bounded retained Compose diagnostic must record:

- supervision policy version;
- hard deadline and stall-window seconds;
- build start/end times and elapsed seconds;
- the last qualifying progress event kind and elapsed timestamp;
- classified build failure reason when applicable;
- candidate build-argument digest or SHA representation sufficient to prove topology binding without adding secrets.

All new evidence values remain bounded, allowlisted, redacted, and checksum-covered. The existing cleanup path still runs on every exit and no final authority is published unless every final predicate passes.

### 4. Dockerfile and Compose boundaries

Each Dockerfile receives a declared build argument named `ACCEPTANCE_CANDIDATE_SHA` after dependency installation and before application source/build work. It may be consumed in a no-op, deterministic layer that does not persist secret data and does not change runtime configuration.

The generated, task-private Compose override owns this argument. Root Compose files, product contracts, adapters, callers, and browser descriptors do not gain a build-argument input. The override must not copy arbitrary environment values into build args.

### 5. Tests and acceptance criteria

Unit tests must prove:

- final build argv uses `--pull` and does not use `--no-cache`;
- task-private rendered override binds every contract service to the exact candidate argument;
- a changed dependency manifest relies on Docker cache invalidation rather than a false cache hit, expressed through Dockerfile/override contract tests;
- repeated non-progress lines do not reset the stall timer;
- new stage, byte advance, and new active `RUN` output do reset it;
- stall and hard-deadline failures have separate reasons, close ledger claims, and block startup;
- image reconciliation and evidence/cleanup behavior remain fail-closed;
- no caller-controlled build args or cache controls are accepted.

A focused non-final build diagnostic may be used to validate streaming classification after implementation. It must preserve the existing no-final-authority rule. A later final lane still requires fresh health, fresh static, pushed exact head, and explicit operator authorization.

## Non-goals

- No persistent remote cache service or registry cache is introduced.
- No unbounded build duration is permitted.
- No dependency version is changed merely to improve build speed.
- No product API, route, ETA, POI, or browser journey behavior changes.
- No final-lane retry is authorized by this design.
