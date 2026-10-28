# Independent review — issue #404 planning assessment

> Archived session evidence from 2026-10-24 at source commit
> `74cbff5146de973c58b5ea0a1c1c76eddb793093`. Local `/tmp` paths and tool chunk
> references below describe the original session; they are not required to use
> this committed handoff. See [the handoff](README.md) for current status.

Status: **DONE**. Commits: none. Corrected assessment is acceptable **as
planning only**; no unresolved review findings. Nothing here authorizes
collection, measurements, implementation or rollout.

Reviewed repository HEAD: `74cbff5146de973c58b5ea0a1c1c76eddb793093`, clean
branch `docs/404-phase3-assessment`, worktree
`/home/oracle-worker/Work/starlink-dashboard/.worktrees/ci404-phase3-assessment`.
Reviewed external deliverable:
`/tmp/orchestrate-404-20261024/reports/assessment.md`, final SHA256
`fae13e4810c28c7f1cf77d73ad5417759398386d1a82d68e369cbfcbf9b4dcff`. Initial
reviewed digest was
`a7be06ce607fc63e8371998efeb02258d0f5c5bcf662d9c7d22417aa28767144`; the same
review assignment included one primary-owned documentation correction and
targeted reread. Policy and original brief read directly. Historical numbers
were checked for faithful attribution to that brief, not independently fetched
or measured.

## Finding R404-01 — resolved: make prospective failure progression fail closed

- Reviewed head: `74cbff5146de973c58b5ea0a1c1c76eddb793093`.
- Location: assessment lines 73–95; corresponding canonical source
  `tools/verify:258–269` and `backend/starlink-location/pytest.ini:14–17`.
- Category/effect/severity: experiment command correctness; **medium**, limited
  to prospective execution readiness. A failed or timed-out serial invocation
  need not prevent subsequent collection when the shown shell snippet is
  executed, and the promised immediate stop on a test failure is not supplied by
  the displayed pytest flags.
- Affected acceptance: **A02**, exact bounded commands and review stops.
- Evidence: the serial command is followed directly by the collection template
  without shell fail-fast or an explicit exit-status guard. Pytest's displayed
  command and tracked addopts contain no fail-fast flag. In contrast, the
  canonical verifier explicitly returns the first command's nonzero status at
  lines 267–268. Assessment line 95 says “Stop immediately on failed tests,
  setup/collection errors, timeout” while the shown serial pytest invocation
  normally completes the remaining suite after an ordinary test failure. The
  future command-sheet review is a useful mitigation, but the proposed exact
  commands should already agree with their stated stop contract.
- Bounded correction: show an explicit nonzero/timeout guard (or fail-fast shell
  runner with cleanup traps) for every invocation and prevent all later
  invocations until owned-resource cleanup is verified. Preserve ordinary serial
  pytest semantics and reword the promise to stop the experiment before the next
  invocation after a failed serial session; if true first-failure termination is
  desired, explicitly review that sampling difference instead. This requires
  report clarification only, with no test execution or new infrastructure.
- Resolution verified against final digest: assessment line 74 now supplies
  `set -euo pipefail`; line 96 explicitly preserves ordinary pytest semantics,
  requires nonzero/timeout checks and abort before later invocations, always
  invokes owned-resource cleanup, and requires runner status/exit/signal review
  before M1. It explicitly identifies the snippet as a baseline rather than a
  complete cleanup runner. This resolves the inconsistency without changing
  tests or authorizing execution. Evidence chunk `c1f40f`.

## Other acceptance findings

**A01 supported.** Direct reads confirm the canonical dev+GFS uv requirements,
tracked Python setup and 3.11 assertion, existing named gates and their source
contract, import-time shared bootstrap paths, function-scoped mission/planning
storage ownership, subprocess sessions and port-0 ownership, SQLite closure,
cross-family imports and cartography mocking. The report correctly treats
directory/AST inventory as distinct from collected items. Its representative
risk table does not claim exhaustive port/network isolation. Historical
4295/4275/20 and 811.10s remain historical; family balance and the five-minute
target are unproven.

**A02 otherwise supported.** M1 is one unchanged serial test execution plus five
sequential collection invocations, with explicit per-command and whole-job caps,
future authorization and review boundaries. Both requirement files and
configured Python are retained. Node-ID multiset reconciliation detects
missing/imported/extra tests without hardcoding historical counts. Separate
fresh runners/whole checkouts avoid the unsafe same-host disk/Cartopy/bootstrap
design. Later overlapping family validation and fail-closed aggregation are
distinguished from the immediate experiment. Missing/cancelled/setup-failed
jobs, artifact identity and partition mismatch block the aggregate;
Static/Frontend and the Backend Test Gate name are preserved. Cost, rollback and
noise limits are explicit.

The small prospective pytest plugin is reasonably scoped to observing collection
and phase durations; it is not an implemented profiler or production sharding
framework. Reviewing that plugin and owned runner command sheet before
authorizing M1 is an appropriate concrete stop. No additional profiling
architecture is needed now.

**A03 supported within reviewer scope.** The report makes no implementation
authority claim and explicitly leaves final approval/cleanup with the primary.
This review changed only the external review file. No application, fixture,
test, dependency, CI or Git changes; no tests/collection/imports, install,
network request, helper, server, Docker, benchmark or runtime resource was
started. Primary remains responsible for final source/status verification and
removal of the clean task worktree.

## Commands, evidence and cleanup

Read-only commands: `cat` original brief/policy/report; bounded
`git status --short --branch`, `git rev-parse HEAD`; bounded `sed`/`nl`/`rg`
reads of `tools/verify`, `tools/tests/test_quality_gate_workflow.py`, workflow,
pytest config, dev/GFS requirements, root/planning/operator/itinerary conftests,
responsiveness/legacy-export/import/cross-family examples; bounded `sha256sum`
and final deliverable tail. All repository/search commands used
`timeout --kill-after=5s 60s`; no tests or collection were invoked. All command
tools returned exit 0. Relevant evidence chunks: `b44935` (identity), `4084f5`
(canonical commands/workflow/config/dependencies), `1a7c74` (root fixtures),
`a36b5b` (planning/import fixtures and workflow contract), `a0d426` (frozen
digest), `b1f498` (cartography, SQLite, owned server), `d74b94` (nonzero
propagation and cross-family imports). A combined read was output-truncated; the
finding and critical source were subsequently read in targeted output.

No persistent PID/PGID, listener, container, network, volume or temporary
runtime was created. Source-reading processes completed. Only owned write: this
retained external review. No cleanup operation against shared resources was
performed.

Final repository status reread remained clean (`e9d895`, exit 0). Final
correction review used only bounded `sha256sum` and `nl`/`sed`, exit 0. No
runtime resources were started during the correction review.
