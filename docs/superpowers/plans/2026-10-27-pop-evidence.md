# PoP Evidence Implementation Plan

> Execute with the implementation skills, test first, and obtain a fresh final
> review.

**Goal:** Resolve #417–#419 without changing live missions or deployment.
**Architecture:** One backend evidence resolver, occurrence-specific
reconciliation, additive status records and explicitly scoped snapshot exports.
**Tech Stack:** Python/FastAPI/Pydantic, React/TypeScript,
pytest/Vitest/Playwright. **Spec:**
docs/superpowers/specs/2026-10-27-pop-evidence-design.md

## Global Constraints

Overview is a customer-facing, 10-foot operational map. Keep diagnostic detail
in Operator. Do not add plan acknowledgement gates. Unknown PoP is not a service
outage. Keep all nine supplied CIDRs exact. Preserve GeoIP separately and never
infer canonical identity from geography. All evidence is synthetic. Work only in
the feature worktree; PR targets dev. Tests have explicit timeouts and task
resources are cleaned up.

## Review Focus

- Re-entry with repeated destinations and sparse samples must not complete
  future occurrences from one observation.
- Cache and IP changes must keep current/status/map/metrics/export evidence
  consistent.
- Static identity remains available when provider GeoIP is absent, stale or
  contradictory.
- Snapshot metadata must not imply a leg used that egress throughout its
  timeline.
- Forecast mismatch and unconfirmed historical windows must not warn of
  indefinitely imminent call interruption.

### Task 1: Backend evidence and static CIDR identity

Files: services/ground_entry_point.py, new services/egress_identity.py, focused
ground-entry tests, provenance metric definitions if needed. Produces
GroundEntryPoint additive fields: pop_id, identity_source (operator_static_cidr
or geoip), matched_cidr, sampled_at/lookup_at (UTC ISO strings), freshness
(fresh/stale), provider_geoip (raw GroundEntryPoint or separate serializable
record), discrepancy. PopObservation freshness/times may be additive; coordinate
and identity data must be atomic.

- [ ] Add failing tests for all nine CIDRs and boundaries, malformed/nonmember
      addresses, contradictory provider GeoIP, no provider data, cached
      corrections, failed changed-IP lookup and freshness.
- [ ] Run focused pytest; expect new assertions to fail.
- [ ] Implement shared mapping using IPv4 network membership and existing
      sourced catalog; implement bounded evidence/cache semantics.
- [ ] Run ground-entry tests; expect pass. Record exact contract for consumers.

### Task 2: Live reconciliation and status lifecycle

Files: services/pop/models.py, services/pop/live.py, mission/pop_status.py,
api/status.py and pop live/status tests. Consumes Task 1 evidence identity and
freshness. Produces explicit superseded/unconfirmed occurrence history, observed
times/residuals and bounded window advisories in status.

- [ ] Write regression tests for skipped predecessors, repeated
      samples/re-entry, early completion, revision, stale/unknown and aliases;
      run to confirm failure.
- [ ] Implement reconciliation preserving occurrence IDs and forecast timings;
      include lifecycle in status. Use the same observation for API marker and
      identity.
- [ ] Run pop and status tests; expect pass.

### Task 3: Presentation and snapshot exports

Files: frontend types/pop.ts, pages/pop-advisory-projection.ts,
OverviewPage.tsx, Operator consumers; backend mission/exporter CSV helpers and
tests. Consumes identity source/freshness and lifecycle from Tasks 1–2.

- [ ] Write failing frontend tests for GeoIP labels, static provenance,
      mismatch/overdue neutral copy, map fields and history; write CSV snapshot
      tests.
- [ ] Implement brief Overview map identity labels and Operator diagnostic
      detail. Rename CSV evidence columns to Mission Snapshot Egress and include
      source/time/provider fields; explicitly label scope.
- [ ] Run focused frontend/backend tests, frontend build and changed-file lint;
      expect pass.

### Task 4: Review, synthetic browser acceptance and delivery

- [ ] Run synthetic browser map and Operator evidence; run isolated production
      checks with configured Docker where available. Record owner/PID/paths
      before resources start and clean them on exit.
- [ ] Run appropriate regression suites and inspect results.
- [ ] Fresh whole-branch code review, resolve material findings and verify.
- [ ] Commit, push feature branch, open PR against dev, verify no task runtime
      resources remain. Preserve acceptance evidence and open PR worktree.
