# V2 Mission Retirement Acceptance Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task by task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a repository-owned, staged acceptance runner that makes one
fresh exact-SHA V2 retirement runtime/browser journey repeatable without making
a no-cache Docker build the cost of every development iteration.

**Architecture:** A small Python stdlib package owns input validation, bounded
subprocess execution, Compose image/build reconciliation, artifact manifests,
and phase orchestration. A focused Node CDP program owns headed Xvfb/Chrome
viewport proof and the real deployed journey. A minimal shell entry point is
only the stable operator command. Generated overrides, browser profiles, and
evidence live outside tracked repository content.

**Tech Stack:** Python 3.11 stdlib and pytest; Bash; Node 22 ESM with
`@playwright/test`; Docker Compose; Xvfb; pinned Chrome for Testing; SHA-256.

**Spec:**
`docs/superpowers/specs/2026-09-23-v2-mission-retirement-acceptance-runbook-design.md`

## File Structure

- `tools/acceptance/v2_mission_retirement.py` — CLI, phase sequencing, elapsed
  timing, stop classifications, and single cleanup owner.

- `tools/acceptance/model.py` — immutable validated inputs, phase enum, command
  result, image record, and manifest DTOs; no subprocess or filesystem writes.

- `tools/acceptance/preflight.py` — bounded identity/ref/detached-worktree and
  sanitized topology commands.

- `tools/acceptance/compose.py` — task override rendering, config inspection,
  BuildKit parsing/reconciliation, image inspection, controls, and Compose
  cleanup commands.

- `tools/acceptance/artifacts.py` — mode-restricted artifact root, retained
  command records, manifest generation, checksum generation/verification.

- `tools/acceptance/browser/v2-mission-retirement.mjs` — Xvfb/Chrome/CDP
  ownership, neutral viewport card, deployed V2 journey, and bounded evidence.

- `tools/run-v2-mission-retirement-acceptance.sh` — shell entry point that
  executes the Python CLI without pipeline logic.

- `tools/tests/test_v2_acceptance_model.py` — pure input/phase/command tests.
- `tools/tests/test_v2_acceptance_compose.py` — override, BuildKit, image, and
  fake-Docker subprocess contract tests.

- `tools/tests/test_v2_acceptance_artifacts.py` — manifest/path/mode/checksum
  tests.

- `tools/tests/test_v2_acceptance_runner.py` — orchestration and phase-isolation
  tests with injected fakes; no real Docker or browser.

- `tools/tests/test_v2_acceptance_docs.py` — documentation route and command
  contract tests.

- `docs/missions/v2-mission-retirement-acceptance.md` — concise operator
  runbook; link it from `docs/missions/README.md`.

## Global Constraints

- Preserve production application behavior, deployment defaults, Portainer/GHCR
  configuration, CI publishing, credentials, and live deployment unchanged.

- Validate a full 40-character SHA and named ref; never accept/normalize an
  abbreviated or whitespace-modified identifier.

- Default phase is `full`; supported phases are `preflight`, `static`,
  `browser-card`, `runtime-cached`, and `full`.

- `static` and `browser-card` must not invoke Docker. `runtime-cached` must be
  manifest-classified non-final and must not claim final acceptance.

- Use `uv` with both backend requirement manifests. Record Black/Ruff versions,
  then invoke exactly `black --check app tests`, `ruff check app tests`, and
  `pytest -q` from `backend/starlink-location`.

- Do not run a standalone frontend build immediately before configured
  Playwright, whose web server already runs `npm run build`.

- `full` runs exactly one `COMPOSE_BAKE=false docker compose ... build
  --no-cache
  --progress=plain` under a >=900-second-capable process owner; it never uses
  `up --build`, concurrent/duplicate builds, or a retry after budget exhaustion.

- On wrapper nonzero/timeout, reconcile each expected service’s `exporting`,
  `naming`, `unpacking`, and final `DONE` log evidence against actual named
  image
  tags/IDs before classifying failure.

- Start only `starlink-location` and `mission-planner` once with `up -d
  --no-build --wait --wait-timeout 180`; do not start Prometheus/Grafana.

- Use an external task override from tracked `.env.example` only. Replace fixed
  root ports/container names, preserve volumes, and never inspect/copy private
  `.env`.

- Browser uses the exact pinned Chrome path from the spec and a task-owned Xvfb,
  profile, CDP port, and process group. No `Emulation.*` metrics/screen
  override.

- Require pre- and post-journey 1920×1080 page/visual viewport, DPR 1, and
  decoded 1920×1080 PNG evidence. Mismatch stops product actions.

- Positive journey proof is Nginx frontend → real backend UI only: Create New
  Mission → Detail → Add Leg → tracked KML upload → Activate → Overview. No API
  seeding, request interception, or direct pre-created-state navigation.

- Evidence is outside tracked content, mode 0700/0600, SHA-qualified,
  checksummed
  and verified after cleanup. Cleanup owns only task browser/display,
  containers/networks, and task temporary files; it preserves volumes.

- Keep each new source/test module below the project cohesion guideline (~300
  lines). Documentation is required in this delivery.

## Review Focus

1. A Docker wrapper timeout after valid exports must inspect both tags and IDs
   and proceed exactly once; a missing export/naming/unpack/DONE signal must
   fail closed. Task 2 owns deterministic parser and fake-Docker tests.

2. A root Compose list merge retaining `5173:80`, fixed `container_name`, or
   private `env_file` invalidates isolation. Task 2 owns resolved-config tests.

3. A neutral display declared as 1920×1080 but an actual browser page at
   1920×937 must stop before the product journey. Task 3 owns the metric/raster
   assertion and neutral-card test.

4. A lower-cost phase must never accidentally invoke a no-cache build or write
   a final-pass manifest. Task 4 owns phase-isolation tests.

5. A cleanup error must not erase a primary failed phase, and retained artifacts
   must remain checksum-valid after cleanup. Tasks 1 and 4 own those tests.

---

## Companion documents

- [Tasks 1–2: Model/artifact contracts and Compose
  reconciliation](2026-09-23-v2-mission-retirement-acceptance-runbook-tasks-1-2.md)

- [Tasks 3–4: Headed browser card and staged
  runner](2026-09-23-v2-mission-retirement-acceptance-runbook-tasks-3-4.md)

- [Tasks 5–6: Operator runbook, exact-head acceptance, and plan
  review](2026-09-23-v2-mission-retirement-acceptance-runbook-tasks-5-6.md)
