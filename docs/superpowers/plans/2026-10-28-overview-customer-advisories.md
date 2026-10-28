# Overview Customer Preset and Shared Advisories Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this
> plan task-by-task.

**Goal:** Add customizable flight-event selection to Overview presets and share
confirmed Operator advisory acknowledgments with passive displays.

**Architecture:** Extend existing shared settings/preset capture with a boolean
flight-only preference and Customer slot. Read complete persisted event
snapshots in an identity-scoped Overview reader, project concise advisories
using backend timing policy, and normalize generated presentation without
changing identity.

**Tech Stack:** Python/FastAPI, React/TypeScript, React Query, Vitest, pytest,
Playwright, production Docker/Nginx.

**Spec:**
[Approved design](../specs/2026-10-28-overview-customer-advisories-design.md),
approved in the session on 2026-10-28. Execute inline under the user's “approved
proceed” instruction.

## Global Constraints

- Shared customizable presets; default `next_flight_events_only=false`; Customer
  is an additive save slot.
- No URL audience mode. No new acknowledgment database, Overview mutation/audio
  controllers or actual transport actions.
- Title Case, Starshield, KA and X-Band; preserve API enums, user text, history
  and occurrence identity.
- Touched times use 24-hour Zulu; preserve customer briefing PDF exception.
- Advisories use backend `threshold_at`, fresh/aligned complete context, and
  confirmed acknowledgment state.
- Visible/hidden receipt-age budgets: 45/150 seconds. Poll events at 15/60
  seconds.
- Bound test/build runs; record/clean task-owned runtime resources; preserve
  primary dev checkout.

## Review Focus

- Old presets must reset the added flight-only field, without losing saved
  bundles or bypassing conflict checks.
- Untimed flight candidates, repeated endpoints and manual destinations retain
  honest ordering/timing.
- Late paginated reads after a leg/store/epoch/run change cannot surface old
  advisories.
- Concurrency-only X and PoP observation diagnostics cannot become outage
  headlines.
- Shared acknowledgment must survive reload and ETA drift, while new material
  occurrences can rearm.

## Task 1: Shared Settings and Presets

**Files:** `app/services/overview_link_settings.py`,
`app/api/overview_link_settings.py`, related backend settings tests; frontend
`services/overview-link-settings.ts`, `overview-preset-actions.ts`,
`components/operator/OverviewPresetsCard.tsx`,
`pages/OverviewLinkSettingsCard.tsx` and related tests.

**Interfaces:** Add `next_flight_events_only: boolean` (default false) to
confirmed settings; add `customer` to preset names. Legacy preset application
supplies false with matching expected baseline.

- [ ] Add failing tests for default/strict persistence, Customer save/apply,
      false fallback on legacy presets and capture of either value in any
      preset.
- [ ] Run focused settings/preset tests and confirm intended failures.
- [ ] Implement additive settings, switch and preset slot; retain existing write
      confirmation/conflict semantics.
- [ ] Run the focused tests and commit.

## Task 2: Flight Selection and Semantic Sections

**Files:** frontend `pages/overview-arrival.ts`, `OverviewArrivalPanel.tsx`,
`OverviewPage.tsx`, corresponding arrival/page tests.

**Interfaces:** Extend `deriveArrivalPanel` with an optional flight-only boolean
after existing clock parameters; add stable `key` to `ArrivalSection`.

- [ ] Add failing tests for mixed transport/flight ordering, untimed/no flight
      candidate, independent map filters and preserved
      manual/phase/landing/replay behavior.
- [ ] Replace label comparisons with section keys, filter typed flight
      candidates before selection, and bind confirmed preference.
- [ ] Render Title Case headings and 24-hour Zulu with date rollover.
- [ ] Run arrival/page tests and commit.

## Task 3: Generated Vocabulary

**Files:** backend mission POI generators, a focused presentation helper,
`app/operator/event_projection.py` and event models; frontend POI/event
presentation consumers and tests.

**Interfaces:** Explicit generated kind vocabulary; structured advisory
classification for concurrency/window/diagnostic distinctions, separate from
title and identity. Read-time legacy name adaptation only for recognized
generated templates.

- [ ] Add table-driven failing tests for every kind, legacy labels, retained
      endpoints/satellite detail, untouched user names and concurrency versus
      unavailable/degraded titles.
- [ ] Update generators and read-time presentation without
      store/history/identity rewrites; remove forced uppercase and touched
      legacy terminology.
- [ ] Run POI generation/projection, ledger/eligibility/ack tests and frontend
      event formatting tests; commit.

## Task 4: Complete Identity-Scoped Overview Advisory Reader

**Files:** frontend `services/operatorEvents.ts`, `types/operatorEvents.ts`, new
`hooks/api/useOverviewAdvisories.ts`, pure `pages/overview-advisories.ts`,
`OverviewPopAdvisories.tsx/.css`, `OverviewPage.tsx`, focused
reader/projection/component tests.

**Interfaces:** Complete `EventSnapshot` validated against
store/epoch/mode/context; active leg scoped query. Pure projection returns
advisory items plus restrained unavailable/stale state; never falls back to raw
PoP data.

- [ ] Add failing tests for all transports/simultaneous events, timing
      thresholds/end, PoP audio exclusion, acknowledged/retired/preview
      suppression and freshness/alignment.
- [ ] Add failing reader tests for terminal truncation, changed mode/run/pages,
      old results/context switch and 409/503.
- [ ] Implement read-only queries with visibility/focus polling and monotonic
      receipt freshness; match active context and event leg/replay, reuse shared
      snapshot reader.
- [ ] Integrate glass-theme strip in both preset configurations, preserve
      diagnostics off Overview, and verify no mutation/audio controller.
- [ ] Run focused reader/projection/page tests and commit.

## Task 5: Production Two-Client Acceptance

**Files:** task-specific acceptance harness under
`tools/acceptance/overview-advisories/`, Playwright journey/config if needed,
evidence under `docs/reports/2026-10-28-overview-advisories/`.

**Interfaces:** Actual candidate SHA through production backend and Nginx,
synthetic raw mission/route/position/model inputs; reuse existing Operator
acceptance fixtures where possible.

- [ ] Record project/process/private path ownership and install bounded-run
      cleanup handlers.
- [ ] Run focused/full appropriate backend/frontend checks, TypeScript build and
      lint; record baseline failures separately.
- [ ] Commit candidate; build/run isolated production images; test
      Customer/custom/legacy presets and two Overview contexts plus Operator
      acknowledgment.
- [ ] Prove polling suppression, reload persistence/history, ETA drift/new
      occurrence, unavailable context/source, desktop/mobile readability and
      keyboard interaction. Preserve screenshots, scenario results and exact
      tested SHA.
- [ ] Stop/reap owned processes and remove private containers/networks/volumes;
      verify cleanup.

## Task 6: Review and Deliver

- [ ] Obtain fresh whole-branch review, resolve substantive findings with
      regression checks.
- [ ] Update design/report/PR to final behavior and validation, inventory
      unrelated Zulu follow-through and give simple revert backout.
- [ ] Push feature branch, update PR #427 against dev and report remaining
      acceptance/CI limitations honestly. Do not merge/deploy.
