# Issue 404: session handoff

Recorded on 2026-10-24 for
[issue #404](https://github.com/bcl1713/starlink-dashboard/issues/404). This
commit preserves the completed sharding and isolation assessment and its
independent review. It does not implement sharding or authorize test runs.

## Read first

- [Assessment and proposed measurement experiment](assessment.md).
- [Independent review and resolved finding R404-01](review.md).
- [Development workflow](../workflow.md) and
  [workspace instructions](../../../AGENTS.md).

## Completed work

Stage 1 was merged through
[PR #409](https://github.com/bcl1713/starlink-dashboard/pull/409). The two Stage
2 investigations were accepted with no code changes: simulated-hour retention
work and ordinary-edit worker lifecycle/import setup were measured as legitimate
cost. This session assessed CI family isolation from unchanged source
`74cbff5146de973c58b5ea0a1c1c76eddb793093`.

The source inventory found 346 test files, 2,805 test-named definitions, and 124
recognized fixtures, all with default function scope. These are syntax counts,
not collected pytest cases. Shared bootstrap paths, process globals,
cross-family imports, subprocess ownership and external cartography data remain
isolation risks. Per-family runtime and a feasible five-minute backend gate are
unproven.

An independent reviewer accepted the assessment after one documentation
correction, R404-01. The proposed runner must stop before later invocations when
a command fails or times out and always clean up its resources, while preserving
normal pytest behavior within each invocation. There are no outstanding
findings.

No backend tests, pytest collection, benchmarks, application changes, CI
changes, sharding, merge, deployment or #391/#408 work occurred in the
assessment. The original assessment worktree and branch were removed after
verification; no runtime resources were launched. The publication worktree stays
while this PR is open.

## Next checkpoint

The recommendation is to measure serial family costs before choosing shards. The
proposed M1 experiment is one bounded serial backend execution and five
sequential family collection invocations, with exact node-ID reconciliation,
separate bootstrap roots, timing and runner-minute accounting, cleanup and no
automatic retries. Review its small observation plugin and owned runner command
sheet, then obtain separate authorization before running M1.

Stop for review after those measurements. Family execution, overlapping
isolation validation and CI implementation require later reviewed scope.
Preserve existing assertions, concurrency semantics and the Backend, Static and
Frontend gates.

## Evidence and publication

The report's CI timings and 4,295 collected / 4,275 passed / 20 skipped are
historical observations, not results from this session. The assessment's
reviewed original SHA-256 was
`fae13e4810c28c7f1cf77d73ad5417759398386d1a82d68e369cbfcbf9b4dcff`. The archived
copies add a provenance notice and Markdown formatting; those file bytes differ
from the original reviewed artifact. Source citations remain pinned to the
source commit above.

Local workflow ID `29013410-c20d-484c-ae9e-44b04e5ddeb6` reached revision 8,
completed status, and a passing structural readiness check. Its internal
checkpoints and tool chunk IDs are supplementary local evidence; this repository
handoff is the durable record and requires no `/tmp` access.

The user then established the delivery standard: planning and investigation
results must also be committed and pushed to the isolated task branch and its
PR. This publication implements that instruction. Keep this worktree while the
PR is open; follow the normal merge and cleanup workflow afterward.
