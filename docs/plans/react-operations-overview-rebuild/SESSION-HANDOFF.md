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
RUNTIME OR BROWSER EVIDENCE:
- exact SHA / environment / result / retained path or not applicable

PRODUCT CONTRACT RESULT:
- live/status lane:
- history bound:
- overlay independence:
- cadence and no overlap/burst:
- 1920x1080 fullscreen:
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
lanes with exact 1/2/5/10/30/paused controls, no overlap or catch-up burst, and
no global Promise.all transaction.

FIRST ACTIONS:
- Inspect the published status DTO/hot path, frontend test harness, App routing,
  API client, Nginx/CSP, overlay endpoints, and current scripts.
- Resolve and test the default cadence and explicit ring-buffer bounds.
- Write the narrow failing status/scheduler tests before implementation.

REQUIRED OUTPUT:
An immutable clean Phase 1 SHA with focused/full checks, deliberate salvage
record, independent specification PASS followed by quality PASS, public PR
handoff, and explicit stop for a fresh Phase 2 session.
```

## Publication mechanics for Oracle

### Phase 0 reset publication

1. Independently inspect the local Phase 0 commit and rerun docs checks.
2. Create/publish `archive/pr-143-pre-simplification-e649ce1` at exactly
   `e649ce169cd5adcbdd83d6264290b30d5221599e`; verify the remote ref.
3. Publish the reviewed Phase 0 commit to existing
   `feature/react-operations-overview`, using the necessary guarded reset
   mechanism because the durable PR currently points at historical work.
4. Read back the remote feature SHA and compare it to the local candidate.
5. Verify the remote baseline diff contains exactly the eight roadmap paths.
6. Post the exact public PR handoff and start Phase 1 only in a new session.

Oracle chooses and executes remote commands. The Phase 0 writer must not push,
create refs, force-update, comment, or otherwise edit GitHub.

### Later phase publication

For each later candidate, Oracle verifies exact SHA, clean checks, ordered spec
then quality dispositions, changed paths, docs impact, cleanup, and supersession
of old evidence before updating the durable feature ref and PR handoff. Phase 3
runtime evidence is regenerated after any code SHA change. Phase 4 integrates to
`dev`; `main` remains Brian-gated.
