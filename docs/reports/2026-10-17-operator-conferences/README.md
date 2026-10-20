# Operator conferences verification

Issue 366, parent 361; PR 377 targets dev. All records, routes, customers and
telemetry in these checks are synthetic. Operator remains disabled by default.
No aircraft, terminal or operational-readiness claim is made.

## Product and source coverage

Reusable conferences, calls and reported customer intervals stay independent.
Establish/Verify/Interrupt/Close affect only the conference. Customer
restoration creates a new interval and retains its interrupted predecessor.
Completing, cancelling or rescheduling calls never closes the shared conference.
A closed or interrupted conference with connected customers shows continuity
unknown.

Intended transport and operator-reported configuration have separate provenance;
neither proves the path carrying a call. Protection uses existing per-leg
timeline PoP windows, continuity intervals and modeled transport segments. The
browser fixture overlaps the real 348 1620–1630Z window and asserts both
advisory and existing modeled planned-outage labels. Saved timelines remain
partial coverage without authoritative current-input alignment, including
equal-clock snapshots. Operator-entered transport-change correlation remains
issue 369; alerts remain 368, broader redesign 376 and operations ZIP
wiring 370. No routing command, approval, blocking acknowledgment or new
notification infrastructure was added.

## Verification

- Full backend canonical gate: **3,977 passed, 20 skipped**. One existing
  Cartopy facecolor warning; Python 3.11.16.
- Full frontend canonical gate: **1,789 passed**, production build passed. Node
  22.22.2; four-CPU affinity bounds Vitest parallelism without changing its
  tests or timeouts. The existing Vite chunk-size warning remains.
- Static canonical gate passed: Black, Ruff, filename policy, Prettier, ESLint,
  Markdown, required internal documentation links and **12 static-policy
  tests**. External HTTP documentation availability remains advisory under
  accepted policy.
- Focused acceptance proof/fixture tests: **20 passed**. The lifecycle test
  drives real 349 multi-leg flight detection, archive sealing and telemetry
  package generation while comparing conference/customer records before and
  after.
- Fresh production backend/frontend images and real Nginx path, Docker 29.8.1,
  actor-owned configured daemon. Candidate
  `1f1012f5b8f50530aeaa126621b169231a84905d`.
- Five production-browser journeys passed: communications, conferences, shared
  display controls, journal and shell. Viewports: 1920×1080, 390×844, 844×390.
- Issue 366 journey covers two overlapping scheduled calls sharing a conference,
  either joining order, interrupted/restored participation, call completion and
  cancellation independence, discrepancy, real PoP-window overlap, two clients,
  a lost acknowledged join response followed by an intervening counterpart edit,
  exact frozen-key/time retry, current-state reread without duplicate records,
  and restart. The mission switch stays disabled while a quick action is
  pending.

[Machine-readable conference proof](conferences-proof.json) records the browser
assertions. The [production summary](summary.json) confirms storage/media/crash
recovery, immutable projections, existing export hashes and complete cleanup.
Raw task-owned logs remain separate.

## Screenshots

- [Desktop 1920×1080](conferences-1920x1080.png)
- [Portrait 390×844](conferences-390x844.png)
- [Landscape 844×390](conferences-844x390.png)

Captures show synthetic discrepancies and separate conference/customer status;
there are no real contacts, addresses, itineraries or operational positions.

## Review and recovery checks

The fresh whole-branch review identified four important implementation issues
and one browser-evidence gap. Regression tests failed first, then passed after
fixes: epoch-change recovery no longer depends on an unrecoverable read-only
call hook; quick actions retain dirty ownership and keys until reconciliation;
restored-store missing records have explicit recovery; clock equality never
establishes fresh coverage. The browser retry includes a counterpart edit before
replay. A clock-read failure before mutation releases the navigation guard.

Additional tests retain drafts when disclosures close or acknowledged saves
cannot reread current state. Connection restoration and tombstone restoration
have distinct labels/audit reasons. New typed links retain same-mission/type
validation, cycle rejection, immutable revisions and dependency-conflict
behavior.

## Compatibility and rollback

No new table or schema migration. Nullable JSON fields preserve unknown legacy
values without rewriting old revisions/receipts. Existing journal projections
include current records and audit history; existing mission/telemetry package
contracts remain unchanged. Preserve a pre-upgrade backup: disabling Operator
rolls back use; older closed-model binaries require restoring that backup before
a binary downgrade, while retaining the newer store separately.

Runtime cleanup passed: no task containers, networks, disposable volumes,
listeners, image tags or child workers remain. The open-PR worktree stays
isolated for review. No merge is authorized by design, plan or native-execution
approval.
