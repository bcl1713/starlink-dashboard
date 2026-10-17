# Operator Journal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking. The approved plan was executed in isolated task scopes.

**Goal:** Deliver #362's editable Operator journal with atomic immutable
history, deterministic simulation, and offline production browser evidence.

**Architecture:** One local SQLite store owns current pointers, complete
immutable revisions, typed relationships, and retry receipts in a single command
transaction. Read-only adapters reuse #348/#349 contracts. Snapshot projections
supply current state, default activity, and optional full audit without another
event framework.

**Tech Stack:** Existing Python/FastAPI/Pydantic/sqlite3,
React/TypeScript/TanStack Query, pytest, Vitest, Playwright, Docker Compose and
production Nginx. No new mandatory dependency or infrastructure.

**Spec:** [Approved design](../specs/2026-10-17-operator-journal-design.md),
including its linked schema, API, and recovery/validation documents. Design
and plan review authorized implementation. Tasks 1–9 are implemented and
verified, including exact-commit production acceptance. See the
[acceptance report](../../reports/2026-10-17-operator-journal/README.md).
Final branch review and pull-request CI remain delivery gates.

## Global Constraints

- `record_id` is a stable backend-generated UUID.
- `version` starts at 1 and increments by exactly one on every accepted
  mutation.
- `OPERATOR_ENABLED=false` by default; store at
  `data/operator/operations.sqlite3`, separate live/simulation paths and run
  IDs.
- Use `journal_mode=WAL`, `foreign_keys=ON`, `synchronous=FULL`, busy timeout 2
  seconds, auto-checkpoint 1000 pages; global then sorted mission then DB locks.
- Lists default to 50, maximum 200; bodies 64 KiB; titles 1–200 characters;
  content notes at most 8000; optional audit notes at most 1000.
- Use `Operator correction`, `Operator removal`, `Operator restoration` when no
  note is supplied; label automatic versus operator-authored reasons explicitly.
- No reason prompt or uncertainty acknowledgment for routine work; UTC displays;
  no actual time more than 60 seconds ahead of the injected acceptance clock.
- Default exports contain `operations/current.json` and
  `operations/activity.jsonl`; `operations/audit.jsonl` is separately requested.
- Preserve Overview, Missions, Configuration and planning/telemetry exports;
  #370 wires package integration; #362 adds projection contracts only.
- Preserve #348 advisories and #349 detection/archive ownership; no actual
  routing verification, aircraft control, measured Ka/X claims, or new auth
  claims.
- Every check has a wall-clock limit and cleanup verification; exact committed
  SHA and offline production Docker/Nginx/browser evidence gate delivery.

## Review Focus

1. Client loses acknowledgment after commit: same key returns the saved receipt,
   while subsequent edits remain intact (Tasks 3, 5, 7).
2. A historical record moves missions during paging/export: no duplicated
   current row or activity attributed to the wrong mission (Tasks 3, 6).
3. Restoring a backup loses newer retry receipts: stale clients must receive
   `store_epoch_changed`, never duplicate an uncertain write (Tasks 4, 5, 9).
4. Wall clock goes backward or actual time is unknown: sequence orders
   knowledge, source freshness stays unknown/stale, and no past alert is
   inferred (1, 6, 8).
5. Store is missing/full while optional feeds fail: preserve drafts, history,
   and baseline pages without false saved indicators or empty-store fallback (4,
   7, 9).

## File and task map

Backend paths below are relative to `backend/starlink-location`; frontend paths
are relative to `frontend/mission-planner`. Tool/doc paths are
repository-relative. Task details list concrete files and public interfaces; new
modules remain small and focused, following the repository's 300-line policy.

| Order | Deliverable                           | Detail document                                               |
| ----- | ------------------------------------- | ------------------------------------------------------------- |
| 1     | Typed contracts and clock             | [Backend tasks](2026-10-17-operator-journal-backend.md)       |
| 2     | SQLite schema and lifecycle           | [Backend tasks](2026-10-17-operator-journal-backend.md)       |
| 3     | Atomic commands and stable reads      | [Backend tasks](2026-10-17-operator-journal-backend.md)       |
| 4     | Recovery, backup and maintenance      | [Backend tasks](2026-10-17-operator-journal-backend.md)       |
| 5     | Gated FastAPI surface                 | [API/editor tasks](2026-10-17-operator-journal-surfaces.md)   |
| 6     | Current/activity/audit projections    | [API/editor tasks](2026-10-17-operator-journal-surfaces.md)   |
| 7     | Small responsive editor and history   | [API/editor tasks](2026-10-17-operator-journal-surfaces.md)   |
| 8     | Deterministic integration fixtures    | [Acceptance tasks](2026-10-17-operator-journal-acceptance.md) |
| 9     | Offline production/failure acceptance | [Acceptance tasks](2026-10-17-operator-journal-acceptance.md) |

## Execution and verification conventions

Execute in dependency order. Task 6 can follow Task 3 but retains this ordering
to keep shared interfaces stable. Keep product work in a new feature worktree
from `origin/dev` after the approved design/plan has landed there. Do not merge
the design PR or start implementation without the applicable user/review gate.
Keep this documentation worktree while its PR is open.

Backend commands run in `backend/starlink-location`. Each backend test step uses

```sh
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest
```

followed by the exact selection in its task. Use task-private
`STARLINK_TEST_DATA_DIR` and `OPERATOR_ROOT` paths, tracked in the runner's
ownership file before execution; preserve shared test/runtime directories.
Frontend commands run in `frontend/mission-planner`, prefixed with
`timeout --kill-after=10s 10m`. Task 9 specifies longer acceptance timeouts.

For each task: first run the named new tests and observe their intended failure,
implement only that deliverable, then run them to green. A failure caused by an
unavailable environment is not the intended red result. Commit only task-owned
files with the stated message after relevant checks. Do not broaden scope or
repeat expensive acceptance without a changed candidate or unresolved concern.

## Plan self-review and handoff

Coverage: schema/time/association → 1–3; atomic state/history and concurrent
clients → 3/5; WAL/retention/migrations/rollback → 2/4; editable operational
views → 7; #348/#349 reuse → 8; default activity and optional audit → 6;
offline/failure/production evidence and cleanup → 8/9. The five Review Focus
conditions have explicit assertions in their owning tasks. All planned
cross-task types are defined in Task 1 or the producing task's Interfaces block.

No generic event bus/outbox, full Operator shell, call scheduling/conference
workflow, reminder implementation, package/import route, or new PoP predictor.
Review this plan and select native or subagent-driven execution before product
implementation. Either selection still requires the prescribed tests, exact-SHA
acceptance, branch review, and PR against `dev`.
