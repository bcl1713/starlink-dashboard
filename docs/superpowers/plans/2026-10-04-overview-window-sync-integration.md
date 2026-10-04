# Issue 257 review-fix integration record

Started at required `b6f6d1ab16719db43eb79c030d99d630fd430045` in the clean
`/tmp/starlink-257` worktree on `feat/257-overview-window-sync`. Remote feature
matched that SHA; remote dev remains `b2ea3341f78137c1409a618c8d8da5814a14dac2`.
Original checkout, other worktrees, all previous contracts/rulings and evidence
are preserved. This session addresses R1/R2 only and hands off separate fresh
independent review; it does not create or merge a PR.

Authority: [review findings](2026-10-04-overview-window-sync-review.md),
[approved design](../specs/2026-10-04-overview-window-sync-design.md),
[main plan](2026-10-04-overview-window-sync.md), and
[session protocol](2026-10-04-overview-window-sync-handoff.md).

## R1 correction and targeted verification

The layout now observes the complete display-controls container and enclosing
right overlays. Desktop fit checks measure the display container instead of
only its Fullscreen button, including identity and dynamic local/remote
feedback. Landscape controls can wrap; the identity does not shrink, and
feedback can wrap within its available width. The existing measurement guards
select stacked/scrolling flow when the compact upper band grows too large.
Sizes, fit thresholds, one-pixel geometry budget, pointer passthrough and
command/
native fullscreen semantics are unchanged. No REST, camera, chart or channel
implementation changed.

Ruling: observe stable containers rather than adding host feedback to the
Overview content key — local Fullscreen feedback belongs to the child component
and also needs measurement — cost if wrong: browser geometry/observer lifecycle
regressions must detect incomplete container measurements. Preserve the earlier
landscape placement ruling; use its existing flow fallback for larger feedback.

New hook regression exercises feedback growth without frame resize or
content-key
change, and verifies observer cleanup. RED: one failed/one passed (landscape
persisted); GREEN with responsive-layout suite: two files/17 tests passed.
New compact browser regression uses the controlled REST fixture at 844×390,
paused follow/GPS unavailable and real native rejection. It checks containment,
nonoverlap, text bounds, matching identity and native local entry/exit with
actual
controller state. CDP observations retain `userGesture:false`; no permission
flags. RED: display container exceeded stage/overlapped arrival. GREEN: one
passed (25.0s). It now separately scrolls guidance into view for its screenshot.
The earlier screenshot captured only the scroll viewport and is not used as
visual evidence of guidance.

[Bounded measured correction](../../reports/evidence/2026-10-04-overview-window-sync/integration.json):
paused remains landscape/flow=false with zero bounds issues; rejection becomes
stacked/flow=true with zero bounds issues. The display ends at 725.78px and
arrival starts at 733.78px in the scrollable map stage. This is controlled
browser evidence, not physical-device acceptance.

Canonical frontend before commit: 90 files/789 tests and production build
passed; changed TypeScript/test ESLint and CSS/TypeScript/test Prettier passed.
Existing chunk advisory remains. Broader browser and frozen-candidate gates are
recorded separately below and are not inferred from this targeted result.

## R2 correction

The investigation's current status now records delivered Tasks 1–4 / Task 5
steps 1–6,
the final 53-test browser pass and remaining review/integration gates. Its
original diagnosis/baseline is explicitly historical; the earlier draft design
statement records subsequent user approval on 2026-10-04. Original reproduction
and diagnosis are preserved. Human prose does not require a behavioral test.

## Frozen candidate evidence and next stage

Full local artifacts remain beneath:

```text
.superpowers/sdd/2026-10-04-overview-window-sync-acceptance/evidence/integration/
```

`layout-red.log`, `layout-green.log`, `compact-red-escalated.log`/trace,
`compact-green.log`/bounds, and `frontend-precommit.log` preserve targeted
RED/GREEN. A sandbox preview startup failure in `compact-red.log` is setup
failure, not behavioral RED. All 100 prior final artifacts were reaudited
against
their manifest: zero mismatches (`prior-evidence-audit.json`).

Freeze the fix/report commit before final
canonical/static/browser/real-production
verification. Save `final-summary.json`, `final-manifest.json`, exact remote and
cleanup checks, and `follow-up-review-handoff.txt` outside Git so final evidence
does not change HEAD. Those files carry actual final outcomes and the required
SHA. A failed gate keeps this integration stage incomplete. The tracked record
reports only verification already observed before the commit.

Next assigned stage after verification: separate fresh independent follow-up
review of R1/R2 and their whole-branch implications against current dev. This
implementation author's testing is not independent review. Keep Task 5 step 7
unchecked until the fresh review verifies gap closure. Final PR/merge remains
subject to acceptance, fresh review, branch protection and exact-head CI.

Carry every earlier limitation: physical dish/provider/GPS/suspension
unaccepted;
valid task simulation 35/-100, GEP 36/-102 only; real X-band visual change
without a
seeded link distinct from controlled projection; Chromium native fixtures
separate from production Nginx; other browsers/physical native windows
unaccepted;
issued native fullscreen has no abort API. Preserve all saved-state, camera/
history, command partition/deadline, heartbeat and four-clock slot contracts.

Runtime: carried Node 22.22.2/npm 10.9.7, Playwright 1.63.0/Chromium
153.0.8010.12.
Configured actor Docker 29.8.1/overlayfs, context default,
`DOCKER_HOST=unix:///run/user/1002/docker.sock` verified without clearing actor
configuration. Proxy/CA/credentials preserved; cloud status capability/policy
snapshot unavailable. No readiness claim beyond observed commands. Commits use
command-scoped Codex identity; no persistent Git configuration. Normal push
only;
no force push, protection bypass, deployment, main promotion or shared cleanup.
