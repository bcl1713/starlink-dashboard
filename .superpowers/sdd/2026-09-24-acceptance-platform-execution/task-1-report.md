# Task 1 report — platform health and fingerprint authority

## Delivered

- Commit: `9383ed5ea09300fdd23b3878cb6a25e6e88dc041` (`feat(acceptance): certify platform health`)
- Added descriptor-bound health orchestration, checksum-bound health fingerprints, private SHA-qualified evidence storage, and a native-CDP neutral browser card.
- Added a product-lane health gate that returns `Outcome.ENVIRONMENT_BLOCKED` without invoking its product executor when health is not passed.

## Files

- `tools/acceptance/platform/evidence.py`
- `tools/acceptance/platform/health.py`
- `tools/acceptance/platform/__init__.py`
- `tools/acceptance/browser/platform-card.mjs`
- `tools/tests/test_acceptance_platform_health.py`

## RED → GREEN evidence

- RED: `pytest -q tools/tests/test_acceptance_platform_health.py` failed at collection with `ModuleNotFoundError: No module named 'acceptance.platform.health'` before implementation.
- GREEN: `pytest -q tools/tests/test_acceptance_platform_health.py` → `5 passed in 0.06s`.
- Regression suite: `pytest -q tools/tests/test_acceptance_platform_*.py` → `61 passed in 0.84s`.
- Syntax checks: `python -m compileall -q tools/acceptance/platform && node --check tools/acceptance/browser/platform-card.mjs` → exit 0.
- `git diff --check` → exit 0 before commit.

## Real-health evidence

- Classified against `tools/acceptance/platform/profiles/default.toml`: `environment_blocked` / `platform profile is deliberately unprovisioned`.
- The probe and browser-card callbacks were assertion guards and were not invoked. Therefore no Docker/Compose product work, browser provisioning, browser launch, static/product command, or V2 journey ran.

## Documentation impact

- None; documentation belongs to Delivery Task 2.

## Concerns

- The administrative default profile intentionally remains unprovisioned, so a passing headed-Xvfb neutral certification cannot yet be produced. Provisioning must occur through the platform administrator’s descriptor-bound browser bundle, not branch code.
- Preserved all pre-existing untracked V2-only runner/report migration inputs; none were staged, modified, or deleted.

## Fix round 1 evidence

- Implemented platform-owned descriptor lifecycle: the verified `BrowserLaunchSpec` starts Chrome with platform-selected Xvfb display and local CDP port; health waits at most 120 seconds for both child liveness and `/json/version`, then starts the generic Node card with only that CDP URL. A single Python `finally` terminates browser/Xvfb, retains both stdout/stderr, and closes launch/bundle descriptors.
- Failure—including the exact default unprovisioned template—now creates the SHA-qualified evidence root before classification, retains `blocked.json`, `fingerprint.json`, `manifest.json`, and `SHA256SUMS`; the unprovisioned regression asserts no probe/product/browser path executes.
- Evidence writes now use no-follow directory/file descriptors, `O_EXCL` files, `0700` nested directories and `0600` files. Node emits base64 payload data only; Python is the exclusive evidence writer. Validation recomputes card bytes, verifies manifest plus `SHA256SUMS`, and rehashes every retained artifact.
- The card uses native `Browser.getWindowForTarget` / `Browser.setContentsSize`, rejects absent native window output, checks inner and visual 1920x1080 plus DPR 1, and uses `createImageBitmap` to decode the screenshot raster before returning data to Python. No Emulation API is present.
- Added deterministic coverage for readiness timeout/cleanup/log retention, exact-template discrimination, no-product unprovisioned block, Node-result parsing, nested permissions/symlink rejection, artifact/card mutation, and visual/native metrics.
- RED: `pytest -q tools/tests/test_acceptance_platform_health.py` -> 8 failed / 2 passed before implementation (missing lifecycle seams, failure evidence, containment, parsing, and card-output constraints).
- GREEN: `pytest -q tools/tests/test_acceptance_platform_health.py` -> 11 passed; `pytest -q tools/tests/test_acceptance_platform_*.py` -> 67 passed; `python -m compileall -q tools/acceptance/platform && node --check tools/acceptance/browser/platform-card.mjs && git diff --check` -> exit 0.
- Real default-template health: `environment_blocked platform profile is deliberately unprovisioned`, with `blocked.json`, fingerprint, manifest, and sums retained at `0600`; no probe was invoked.
- Module lines: health 228; evidence 172; card 35; tests 210. Documentation impact remains none; Task 2 remains the owner of product/Compose execution.
