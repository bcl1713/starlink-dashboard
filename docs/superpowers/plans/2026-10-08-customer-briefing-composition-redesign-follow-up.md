# Customer Briefing Composition Redesign Follow-up Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Extend the visually accepted primary composition to complete customer
exports with measured budgets, exact evidence, and production qualification.

**Architecture:** Reuse the approved customer view and page geometry. Generalize
material grouping and page planning, publish PPTX/evidence atomically, and
qualify the final candidate without changing canonical availability or legacy
exports.

**Tech Stack:** Python, python-pptx, pytest, existing offline map renderer,
Docker Compose, pinned LibreOffice/Poppler, platform browser acceptance.

**Spec:**
[Approved composition redesign](../specs/2026-10-08-customer-briefing-composition-redesign.md).

## Global Constraints

All exact
[global constraints, file interfaces, ownership rules and commands](2026-10-08-customer-briefing-composition-redesign.md)
from the checkpoint plan apply here. In particular: trial default-off, PR #309
draft, no merge/rebase, maximum three pages per leg, fewer than fifteen for the
five-leg mission, unchanged canonical unknown states, and atomic artifact pair.

## Review Focus

Use the five named input classes and their owning tests in the checkpoint plan.
Tasks 3–5 below complete their generalized coverage.

## Required entry gate

Do not start any task below until the customer explicitly accepts the rendered,
fully assessed primary page from Task 2. Plan approval alone does not satisfy
this gate. Preserve the execution method selected for the checkpoint plan.

## Task 3: Material grouping, changing uncertainty, and human clock edges

**Files:** Modify `customer_view.py`, `customer_clocks.py`, their unit tests,
and `tests/unit/test_trial_pptx.py`; add focused synthetic fixture variants
under `tests/fixtures/customer_briefing/` as required.

**Interfaces:** Uses and extends Task 1 functions without changing their
signatures. Canonical intervals/clocks stay intact. All customer rows retain
their source/interval mappings for Task 5.

- [ ] After visual approval, write parametrized
      `test_material_grouping_never_crosses_operational_boundary`: cover quiet
      gaps, leg boundaries, nested Ka/X outages, subminute total outage, AR
      start/ end, changed restrictions, changed causes/limitations, and changed
      uncertainty. Compare grouping by semantic state/cause/confidence rather
      than source IDs; every material span maps exactly once and remains visible
      in the timeline.
- [ ] Write `test_changing_uncertainty_keeps_boundaries_and_explanation` and
      `test_none_confirmed_with_unknown_is_not_total_outage`: use
      `No transport confirmed available` while any transport is unknown; never
      `Communications unavailable`. Preserve Ka/Starshield outage rows, suppress
      unchanged missing-planning-only rows, and show other coordination
      limitations such as usable X/Ku concurrency. SOF/AR cannot change
      transport counts.
- [ ] Write `test_customer_clocks_midnight_dst_and_precision_collisions`: assert
      date labels at midnight, explicit EST/EDT or offsets for repeated local
      times, seconds for material minute-label collisions or windows under one
      minute, and outward-rounded fractional seconds with no microseconds.
      Include spring/fall DST, a flight longer than 24h, and short-flight SOF
      overlap. Assert leg-local T-zero and unchanged exact UTC duration; sparse
      Zulu/T-plus anchors remain secondary, not repeated full timestamps.
- [ ] Run RED, implement customer-only grouping and clock refinements, and run
      the new suite plus unchanged canonical tests GREEN. Re-render the approved
      pair if typography or its appearance changes. Commit
      `feat: preserve material briefing windows and human clock precision`.

## Task 4: Measured continuation, incomplete legs, and page budgets

**Files:** Modify `customer_pages.py`, `trial_layout.py`, `trial_pptx.py`;
create `tests/unit/test_customer_pages.py`; extend deck tests and fixtures with
dense/long and representative five-leg inputs.

**Interfaces:** Completes `plan_customer_pages` for ordered multi-leg input.
Plans use one-based slide numbers and stable row IDs, shared by PPTX/evidence.
Capacity failures raise existing `TrialGenerationError` with a local diagnostic
cause; they do not return a truncated deck.

- [ ] Write `test_normal_leg_is_not_split_by_internal_interval_count`,
      `test_dense_leg_has_at_most_three_pages_and_rows_once`, and
      `test_five_leg_budget_is_strictly_less_than_fifteen`. The primary contains
      full-leg summary and table; continuation retains leg/time context with
      remaining rows once. Timeline splitting is permitted only after measured
      full-leg readability fails and yields consecutive explicitly ranged
      panels. Target six-to-twelve slides without adding filler to a
      five-primary-page mission. Default to no index; an index is never needed
      for these fixtures.
- [ ] Write `test_incomplete_leg_has_one_concise_primary_notice` and
      `test_long_labels_or_material_content_over_budget_fail_atomically`:
      missing timing/endpoints/map cannot add diagnostic pages. Arbitrary raw
      source text remains evidence; genuine customer limitations cannot be
      dropped or made smaller to fit. Reject duplicate/mismatched leg/map IDs
      before rendering and preserve mission leg order.
- [ ] Run RED. Add measured row packing at 14–16 pt and continuation planning;
      keep approved primary geometry where it fits. Make validators enforce
      role-specific fonts, leg/mission budgets, plan coverage, and native
      objects. Run all customer/canonical/deck tests GREEN; commit
      `feat: bound customer briefing pages without losing material windows`.

## Task 5: Separate exact evidence and atomic optional artifact pair

**Files:** Create `customer_evidence.py` and
`tests/unit/test_customer_evidence.py`; modify
`backend/starlink-location/app/mission/package/__main__.py`,
`tests/unit/test_trial_package.py`, `test_trial_export_endpoint.py`, and
`tools/acceptance/customer-briefing/inspect_pptx.py`; update relevant acceptance
tests that previously located exact provenance inside PPTX text.

**Interfaces:** Produces the two evidence functions in the interface map. Add
frozen `TrialArtifacts(pptx: bytes, evidence: bytes)` in package assembly;
change private `_build_trial_export(snapshot)` to
`tuple[TrialArtifacts | None, tuple[str, ...]]`. This is internal only; update
its tests/probes. Add `EVIDENCE_PATH` with the exact required ZIP path.

- [ ] Write `test_evidence_is_exact_versioned_and_complete`: assert
      `schema_version=1`, snapshot fingerprint, ordered leg IDs, exact ISO UTC
      bounds, unchanged ET/Zulu/T-plus from `format_clocks`, decisions/rules,
      confidence (`assessed` or `incomplete` from the actual decision tuple),
      source references and unsplit original records, restrictions, map status/
      warnings, row mappings and one-based slide assignments. Include sources
      that create no customer row. Serialization must be deterministic and read
      only the passed snapshot/projection/map/view/page inputs.
- [ ] Write `test_evidence_rejects_missing_or_mismatched_references`: reject
      wrong fingerprint/leg order, unknown row/interval IDs, uncovered material
      rows, invalid slide assignments, and exact-time changes. Keep renderer
      identities/diagnostics and full raw source payloads outside customer
      content.
- [ ] Write `test_trial_pair_is_atomic_for_every_failure_stage`: fault view,
      planning, PPTX creation/validation, evidence creation/validation; assert
      both optional paths and manifest entries absent, legacy ZIP
      readable/complete, safe failure status/warnings intact. Success lists both
      paths; disabled exports retain the original file set and manifest
      contract. Mutating live managers after capture cannot change either
      artifact's fingerprint/content.
- [ ] Run RED. Build views/pages once in `_build_trial_export`, pass the same
      objects to PPTX and evidence, validate both in memory before adding either
      to ZIP/manifest. Preserve package/HTTP/UI return types and safe warning
      feedback; keep detailed failure causes in local diagnostics. Implement
      exact evidence validation, update inspections, run
      package/snapshot/endpoint tests GREEN, and commit
      `feat: publish briefing evidence atomically with trial deck`.

## Task 6: Production qualification and customer review package

**Files:** Modify `tools/acceptance/customer-briefing/generate.py`,
`backend_probe.py`, `direct_export.py`, `inspect_pptx.py`, `render_decks.py`,
`README.md`, and `tools/tests/test_customer_briefing_runner.py` as needed;
create `tools/acceptance/customer-briefing/composition-evidence.json` containing
portable synthetic/checkpoint pointers only. Preserve old evidence reports as
history; do not relabel them as qualification of this candidate.

**Interfaces:** Existing `generate.py`/`run.sh` CLI remains unchanged. The
runner inspects the new pair, validates exact evidence against canonical inputs
and delivered native objects, and records current-candidate gates separately.

- [ ] Write runner tests for optional-pair ZIP/manifest membership, page
      budgets, full source mappings, native title/table editability, no source
      appendix, qualified uncertainty, and failure-path cleanup. Keep canonical
      synthetic capture cases distinct from normal import/rebuild HTTP exports.
- [ ] Run RED, update inspection/fixture assertions and review selection, then
      run focused tools suite GREEN. Run canonical repository static/backend/
      frontend gates and mission-export asset build with recorded ownership and
      explicit wall limits. Fix failures within this redesign's scope; report
      unrelated failures without suppression. Commit a clean candidate.
- [ ] Use the existing runner with full candidate SHA, new private evidence/task
      paths, free task port, provisioned browser profile when available, and
      `timeout --kill-after=10s 45m`. Build fresh isolated production images and
      run Nginx enabled/disabled/fallback exports, source
      preservation/re-import, fixed-clock legacy comparison, paired
      PPTX/evidence assertions and real browser download/warning journeys.
      Record unavailable authority as blocked; `--api-only` is explicitly
      diagnostic and does not qualify the UI gate.
- [ ] Render normal, incomplete-X, dense/long, five-leg and clock-edge outputs
      offline at full resolution in color/grayscale. Record actual slide counts,
      exact interval/evidence mappings, all material rows once, real rendered
      observations, map warnings and any layout-budget fallback reasons. Confirm
      task process/listener/container/network/private-volume teardown.
- [ ] Deliver revised paired decks, evidence, previews and verification report
      on draft PR #309; require CI at its exact head and preserve recorded
      branch conflicts as unresolved. Record customer scan timings for reduced
      capability, lost/remaining transports and SOF/AR without explanation,
      explicit visual/ semantic acceptance, and desktop PowerPoint version with
      offline title and table-cell edits. Unperformed manual checks remain
      pending.
- [ ] Stop at customer review. No merge, trial promotion, legacy replacement, or
      phase-two work follows from technical success. Keep the open-PR worktree
      and private acceptance evidence; leave no task-owned runtime resources
      alive.
