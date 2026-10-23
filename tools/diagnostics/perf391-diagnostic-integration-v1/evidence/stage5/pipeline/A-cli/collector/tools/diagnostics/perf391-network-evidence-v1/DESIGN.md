# Supplemental network evidence v1 design and implementation plan

This implements the bounded tooling authorization in
[the orchestrator review](https://github.com/bcl1713/starlink-dashboard/pull/406#issuecomment-6348817582).
All files belong to this separate package. No production imports, patches,
frozen-runner edits, benchmarks, merge or deployment are part of this task.

The package records schema-validated JSONL, body artifacts, explicit coverage,
process-local monotonic clocks and correlation IDs. A Python recorder bounds
event bytes/count and total disk usage. A passive browser adapter observes
existing traffic without routing, issuing requests or changing polling. An
optional diagnostic SDK exposes worker and admission timing for a separate
synthetic build; it never installs itself into an application. Legacy trace
imports preserve their own identities and missing boundaries.

The independent analyzer joins exact IDs, rejects ambiguous durations and never
subtracts clocks across domains. Chart analysis compares stored samples,
evaluation coordinates, API payload, projected/plot arrays and separately
attested visible intervals. Missing paint evidence means unknown presentation.
Finite evaluation values cannot prove fresh ingestion. Raw and rollup traces,
viewer/request identities and seeded/measured segments stay distinct.

Implementation tasks (inline execution):

1. Write failing schema/recording tests; implement closed v1 schema, recorder,
   clock anchors, drop/byte accounting and artifact budgets. Verify rejection of
   future versions, malformed records, NaNs and ambiguous clocks.
2. Write failing join/gap tests and immutable synthetic fixtures; implement
   conservative timing, grid, data/projection/render classification and reports.
3. Write failing adapter/lifecycle tests; implement passive browser evidence,
   source observer, host/cgroup snapshots, diagnostic SDK and legacy
   composition.
4. Run bounded offline regression; publish hashes, actual results, unavailable
   coverage and qualification/calibration proposal. Verify isolation and
   cleanup, commit, push and open a separate draft PR against dev for checkpoint
   review.

Review focus: duplicate IDs/boundaries; restarted clocks; absent
instrumentation; out-of-order responses; finite lookback over missing scrapes;
byte limits and pending browser callbacks during cleanup. Each needs an explicit
regression.

Shared interfaces: all adapters produce the same Event envelope; recorder and
analyzer both use the schema validator. Body artifacts use SHA-256 of exact
bytes, never a JSON reserialization. Offline reports remain supplemental and
make no frozen acceptance decision.
