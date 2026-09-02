# React Operations Overview Session Handoff

Copy this file's template into each phase handoff. Replace placeholders only
with observed values; never guess a future SHA, review, check, or publication
result.

## Immutable project facts

- Repository: `bcl1713/starlink-dashboard`
- Durable PR: `https://github.com/bcl1713/starlink-dashboard/pull/143`
- Base ref: `dev`
- Feature ref: `feature/react-operations-overview`
- Clean rebuild baseline: `07593c69040ad447000bf526d6453ec5c6faacfa`
- Historical old head: `e649ce169cd5adcbdd83d6264290b30d5221599e`
- Expected archive ref: `archive/pr-143-pre-simplification-e649ce1`
- Master roadmap:
  [`../2026-09-02-react-operations-overview-rebuild.md`](../2026-09-02-react-operations-overview-rebuild.md)
- Product contract: [`00-product-contract.md`](00-product-contract.md)
- Orchestration: direct/manual, no Kanban; one branch writer
- Publication/archive/PR owner: Oracle
- `main` release owner/gate: Brian

The old implementation is historical, never the incremental base. Selective
salvage requires deliberate review from the archive; never wholesale cherry-pick
it.

The refresh choices are unconditionally `1/2/5/10/30/paused`; `1s` is the
default and fastest. Phase 1 implements and tests this contract and does not
decide it.

## Copy-pasteable phase handoff template

```text
PHASE:
STATUS: PASS | FAIL | BLOCKED
UTC DATE/TIME:
SESSION ROLE: writer | specification reviewer | quality reviewer | accepter

REPOSITORY: bcl1713/starlink-dashboard
PR: https://github.com/bcl1713/starlink-dashboard/pull/143
BASE REF: dev
FEATURE REF: feature/react-operations-overview
ARCHIVE REF: archive/pr-143-pre-simplification-e649ce1
INPUT SHA:
OUTPUT SHA:
OUTPUT SHA PUBLISHED BY ORACLE: yes | no | not yet
WORKTREE CLEAN AT OUTPUT: yes | no

OBJECTIVE:
IN SCOPE:
OUT OF SCOPE:
CHANGED PATHS:
SELECTIVE ARCHIVE SALVAGE: none | list fragment and adoption rationale

RED EVIDENCE:
- command / expected failure / observed result
GREEN FOCUSED CHECKS:
- command / exit status / useful test count
FULL CHECKS:
- command / exit status / useful test count
BOUNDED RUNTIME OR BROWSER RESULTS:
- exact SHA / environment / raw result summary or not applicable

PRODUCT CONTRACT RESULT:
- live/status lane:
- scheduler numeric oracles:
- history/backfill triggers and 30-minute bound:
- overlay independence:
- cadence and no overlap/burst:
- exact one-screen inventory and 1920x1080 fullscreen:
- same-origin/CSP/no arbitrary upstream:
- no GEP IP:
- Grafana fallback/no React request:

SPECIFICATION REVIEW:
- reviewer/session:
- exact SHA:
- PASS or findings:
QUALITY REVIEW:
- reviewer/session:
- exact SHA:
- PASS or findings:

DOCUMENTATION IMPACT:
CLEANUP PERFORMED AND VERIFIED:
UNRESOLVED QUESTIONS OR COVERAGE GAPS:
PUBLIC PR HANDOFF TEXT/LOCATION:
NEXT STEP:
STOP CONFIRMED: yes | no
```

## Concrete Phase 1 kickoff

Use this section only after Oracle publishes Phase 0. The Phase 1 session must
replace `<ORACLE-PUBLISHED-PHASE-0-SHA>` with the verified remote SHA; the
placeholder is intentional because Phase 0 cannot invent its future published
identity.

```text
PHASE: 1 — Independent Live Data
INPUT SHA: <ORACLE-PUBLISHED-PHASE-0-SHA>
EXPECTED BASE: dev
EXPECTED FEATURE: feature/react-operations-overview
EXPECTED ARCHIVE: archive/pr-143-pre-simplification-e649ce1
PR: https://github.com/bcl1713/starlink-dashboard/pull/143

START GATE:
1. Fetch refs without changing another worktree.
2. Verify feature ref equals INPUT SHA and INPUT SHA descends from
   07593c69040ad447000bf526d6453ec5c6faacfa.
3. Verify the INPUT SHA diff from the baseline contains only the eight Phase 0
   roadmap files.
4. Create/use one isolated Phase 1 worktree; require clean status.
5. Read the master roadmap, 00-product-contract.md,
   02-phase-1-live-data.md, and this handoff.
6. Confirm Oracle archived old SHA
   e649ce169cd5adcbdd83d6264290b30d5221599e at
   archive/pr-143-pre-simplification-e649ce1.
7. Do not merge/cherry-pick the archive. Record any selectively adopted fragment
   and review it as new work.

OBJECTIVE:
Build independently scheduled /api/status, bounded local history, and overlay
lanes with exact 1/2/5/10/30/paused controls, `1s` default/fastest, one recursive
monotonic timer, bounded browser timeout, the binding numeric timing oracles, no
overlap/replay/catch-up burst, and no global Promise.all transaction. Bootstrap
history once; reconcile on detected resume/reconnect gaps and explicit manual
request; seed/repair only 30-minute buffers, never current values.

FIRST ACTIONS:
- Inspect the published status DTO/hot path, frontend test harness, App routing,
  API client, history query/DTO, Nginx/CSP, required map/POI/GEP sources, and
  current scripts.
- Implement and test the fixed `1s` default and 30-minute ring-buffer bounds.
- Decide/test only whether constant identity is a deployment-wide backfill guard
  or is removed; do not reopen product cadence or inventory decisions.
- Write the narrow failing status/scheduler tests before implementation.

REQUIRED OUTPUT:
An immutable clean Phase 1 SHA with focused/full checks, deliberate salvage
record, independent specification PASS followed by quality PASS, public PR
handoff, and explicit stop for a fresh Phase 2 session.
```

## Publication mechanics for Oracle

### Phase 0 reset publication

Oracle substitutes only the reviewed local candidate SHA. The historical SHA is
the lease value, not a floating observation:

```bash
HISTORICAL=e649ce169cd5adcbdd83d6264290b30d5221599e
: "${CANDIDATE:?export CANDIDATE to the reviewed local Phase 0 SHA}"
FEATURE=refs/heads/feature/react-operations-overview
ARCHIVE=refs/heads/archive/pr-143-pre-simplification-e649ce1

git fetch origin
test "$(git ls-remote origin "$FEATURE" | cut -f1)" = "$HISTORICAL"
git push origin "$HISTORICAL:$ARCHIVE"
test "$(git ls-remote origin "$ARCHIVE" | cut -f1)" = "$HISTORICAL"
git push --force-with-lease="$FEATURE:$HISTORICAL" \
  origin "$CANDIDATE:$FEATURE"
test "$(git ls-remote origin "$FEATURE" | cut -f1)" = "$CANDIDATE"
REMOTE_CANDIDATE=$(mktemp)
git fetch origin "$FEATURE"
git diff --name-only 07593c69040ad447000bf526d6453ec5c6faacfa...\
"$(git rev-parse FETCH_HEAD)" | sort >"$REMOTE_CANDIDATE"
diff -u <(printf '%s\n' \
  docs/plans/2026-09-02-react-operations-overview-rebuild.md \
  docs/plans/react-operations-overview-rebuild/00-product-contract.md \
  docs/plans/react-operations-overview-rebuild/01-phase-0-contract-reset.md \
  docs/plans/react-operations-overview-rebuild/02-phase-1-live-data.md \
  docs/plans/react-operations-overview-rebuild/03-phase-2-fullscreen-layout.md \
  docs/plans/react-operations-overview-rebuild/04-phase-3-runtime-acceptance.md \
  docs/plans/react-operations-overview-rebuild/05-phase-4-docs-and-integration.md \
  docs/plans/react-operations-overview-rebuild/SESSION-HANDOFF.md | sort) \
  "$REMOTE_CANDIDATE"
rm -f "$REMOTE_CANDIDATE"
```

Archive creation and remote readback must finish before the guarded reset.
Candidate SHA readback and the exact eight-path remote diff must finish after
it. An unguarded `--force` push is forbidden.

Oracle chooses and executes remote commands. The Phase 0 writer must not push,
create refs, force-update, comment, or otherwise edit GitHub.

### Later phase publication

For each later candidate, Oracle verifies exact SHA, clean checks, ordered spec
then quality dispositions, changed paths, docs impact, cleanup, and supersession
of old evidence before updating the durable feature ref and PR handoff. Phase 3
runtime evidence is regenerated after any code SHA change. Phase 4 integrates to
`dev`; `main` remains Brian-gated.
