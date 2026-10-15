# SIGMET encounter timing contracts

Companion to the [implementation plan](2026-10-15-sigmet-encounter-context.md).
These interfaces preserve the approved plan; they are separated to keep its
implementation checklist within the repository's file-length limit.

## Task 1 interfaces

**Interfaces:** `EncounterPlan` is frozen and contains `context_key`, `revision`
(SHA-256), `method` (`segment-linear-utc-v1`), `source` (`ordinary` or
`simulation`), nullable `source_revision` and an ordered immutable tuple of
UTC-millisecond timestamps or null with per-point
`missing-timing`/`invalid-timing` reason. Known precision is `minute`, `second`,
or `unknown`; do not invent precision. Add excluded internal
`encounter_plan: EncounterPlan | None` to `RouteContext`; wire geographic
context remains unchanged.

`capture_encounter_plan` takes `route: ParsedRoute`, `context_key: str`,
`source: str` and `source_revision: str | None`, returning `EncounterPlan`. It
consumes the already deep-copied effective route. Source revision uses its
explicit content hash when available, otherwise null; digest ordered
times/reasons/precision and method too. `evaluate_encounters` takes
`plan: EncounterPlan | None`, `spans: list[IntersectionSpan]`,
`valid_from_ms: int` and `expires_at_ms: int`, returning `EncounterEvidence`. It
consumes existing ordered spans.

`EncounterEvidence` contains `spans: list[PassageEvidence]`, `status`
(`overlap`, `no-overlap`, `unknown`), `unknown_count` and nullable `reason`.
`PassageEvidence` contains nullable integer `entry_ms`/`exit_ms`, status and
nullable reason (`missing-timing`, `invalid-timing`, `ambiguous-association`,
`unavailable-plan`). Known evidence requires both ordered times and null reason;
unknown requires both null times and nonnull reason. Out-of-range segment
indices are ambiguous-association. Evidence has exactly one item per input span.

## Task 2 interfaces

**Interfaces:** Consume Task 1 capture/calculator. Each geographic entry
requires `encounter: EncounterEvidence`. Snapshot schema becomes
`route-sigmets-v2`; add nullable `encounter_plan` containing
revision/method/source/source_revision (no point arrays), `service_instance_id`
(bounded UUID), and `observation_revision` (nonnegative safe integer). Both GET
and selection's internal snapshot use the same contract; mutation wire
confirmations stay as-is.

Under the existing active-leg gate, increment observation_revision whenever
captured geometry or encounter revision changes, including A→B→A. Allocate a
fresh service_instance_id per service lifetime. No-route uses null plan. Recheck
observation revision after awaits and before returning; superseded work returns
an explicit fresh evaluating snapshot, never old evidence with a new token.

## Task 3 interfaces

**Interfaces:** Zod mirrors Task 2 fields and invariants, including total result
size and aggregate span caps. Preserve mutation types and paths.
`formatSigmetEncounter` takes `entry: RouteSigmetEntry | SelectedSigmetEntry`
and `nowMs: number`, returning `string[]`. It returns concise lines;
`SigmetEncounterDetails` accepts `{entry, nowMs}` from the same admitted
snapshot and lists readable crossing windows without implementation metadata.
Share these between Overview attention and Configuration rows/details. This
supersedes the original technical-detail display following the user’s in-flight
review.
