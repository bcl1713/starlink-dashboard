# SIGMET attention review

The Overview stays empty when no advisory needs attention. Otherwise it shows
`SIGMETS: N` and up to three concise cards with matching map highlights and
bright borders. New attention pulses unless reduced motion is requested.
Configuration contains relevant pending and cleared intersections, with full
reports collapsed. Clicking any eligible SIGMET polygon selects it for shared
attention until acknowledgement, cancellation or expiry; selected-only reports
are labelled Selected and never receive manufactured route spans.

Implementation builds on route-linked SIGMET PR #337 (candidate `1319b56d`).
The follow-up targets `dev` and retains that prerequisite until it merges.

## Verification

- Backend complete scientific environment: **3309 passed, 20 skipped**; one
  existing plotting warning. Includes persistent selection, migration,
  cancellation, absent reports, atomic concurrency and bounded storage.
- Frontend: **220 files, 1622 tests passed** after final review fixes.
- ESLint and production TypeScript/Vite build passed. Vite retains the existing
  large-chunk advisory.
- Pinned Ruff 0.16.8 passed on changed backend modules and tests; 29 API/state
  tests passed again after formatting-only corrections.
- Acceptance runner controls and dedicated fixture tests: **31 passed**.
- Exact production candidate: `e1d5dc6f39c3ef47b12c4d421c7b68a04a571943`.
  All **four production browser tests passed** (3.2 minutes). The subsequent
  evidence commit changes documentation only; it claims no separate image run.
- Production cleanup: no containers, networks, volumes, processes or listeners;
  disposable source removed. All five attention proof flags are true, with no
  browser errors. Desktop/mobile screenshots were visually checked for
  readability, clipping, bright borders and empty layout.

## Retained acceptance evidence

Run directory (relative to the preserved feature worktree):

```text
test-results/route-sigmets-3078c3f02557/e1d5dc6f39c3ef47b12c4d421c7b68a04a571943/
```

`PASS.json`, `proofs.json`, `candidate.json`, `images.log`, `browser.log`,
`cleanup.json` and the `playwright/` screenshots/traces retain production
provenance and cleanup evidence. Screens include quiet, selected-only and
pending Overview, plus Configuration Pending/Cleared at desktop and mobile
sizes. Source capture and normalization provenance are retained in the same
run directory.

Earlier failed runs are preserved under `test-results/route-sigmets-57122220c0b1/`
and `test-results/route-sigmets-ceefcb149962/`. Their cleanup receipts also show
no remaining resources. The first exposed frame synchronization and cancelled
fixture reuse; the second exposed a responsive screenshot target remount. The
final run uses fresh-series fixture identities and bounded DOM reacquisition.

## Independent review and decisions

The single whole-branch review found six actionable issues. Each has a failing
regression and a passing fix; none was deferred:

1. An open inspection could reselect a remotely acknowledged report or select
   into a replacement route. One inspection now consumes one intent, bound to
   its original route and report.
2. Keyboard choices missed visible polygons whose source vertices were all
   outside the viewport. Visibility now clips rendered native triangles against
   the camera frustum and checks globe occlusion.
3. Mutation caches retained full snapshots outside the source budget. Selection
   extracts a compact confirmation while the transfer allocation is held,
   releases it, and refreshes through the shared source.
4. Inspecting an already pending report did not focus its card. Explicit
   inspection now focuses the correct page, including repeated clicks.
5. Paging cards did not page map emphasis. Both consume the same visible page.
6. Selecting a station report narrowed away alternate reports. METAR and TAF
   choices now remain available.

The reviewer initially rated items 4–6 Minor; execution treated them as Important
because they affect the requested interaction. Visibility performance had no
measured finding, but a camera/data/viewport/validity cache was added with the
geometry fix. Prerequisite-only behavior remains under PR #337's review.
Runtime lifecycle verification remains the executor's responsibility.

Additional implementation decisions:

- Acknowledged selected-only records retain bounded identity/revision history,
  with selection disabled, until expiry.
- Selection candidates expose bounded authoritative identities for eligible
  map reports; they do not add a Configuration catalogue.
- A temporary partial feed retains manual selection. Explicit cancellation,
  acknowledgement and expiry end it. Only selected reports persist cancellation
  relation metadata, preserving computed-only storage capacity.
- The independent attention scenario uses a fresh bulletin series: replaying
  an old cancelled bulletin correctly preserves real cancellation memory.

## Live preview and ownership

User-requested preview remains at:

- <http://10.10.50.30:15279/overview>
- <http://10.10.50.30:15279/configuration> (Weather tab)

Frontend service `starlink-sigmet-live-frontend.service` belongs to the
`oracle-worker` user. Private Compose project `starlink-sigmet-lan-review` owns
the reloadable backend and its private data. Both follow the implementation
worktree without resetting the user's acknowledgements. Ownership is recorded
in `.worktrees/sigmet-lan-review/.review-runtime/owner.json`.

Stop only this preview with:

```bash
/home/oracle-worker/Work/starlink-dashboard/.worktrees/sigmet-lan-review/.review-runtime/stop-live.sh
```

The same-URL live preview replaces the plan's proposed second review instance,
following the user's explicit request to watch ongoing changes. Only that
requested service is retained. Acceptance uses independent disposable projects.

## Scope and limitations

Relevance means geographic route intersection; it does not assert matching
flight altitude or forecast encounter time. Unknown reports do not create
attention automatically. Real-source acceptance replays the retained dated AWC
capture; it does not claim live upstream availability. Browser acceptance uses
software WebGL in this environment.
