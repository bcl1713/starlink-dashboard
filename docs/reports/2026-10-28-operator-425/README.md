# Operator workspace acceptance — issue 425

The coherent Operator workflow is implemented in
[PR #428](https://github.com/bcl1713/starlink-dashboard/pull/428), against
`dev`. Application candidate: `4b7da4d89cec22a92d52f148ce4fa5ec079d7c7d`. The
following report commit adds evidence only; it does not change that application.

## Result and scope

Operations combines Now and Communications, with a shared mission timeline,
conference and call lanes, a next-action entry, and persistent Schedule, Issue
and Note capture. Transport, Issues, Notes and History retain the same mission
context. Existing URL aliases, display controls, corrections, history and save
recovery remain available. The
[action parity map](../../superpowers/plans/2026-10-28-operator-425.md#current-action-parity-map)
records where existing actions moved.

Establish includes the two-way distant-end check. Direct connections use their
own transport without a fabricated conference. Connect Customer follows accepted
establishment. Eligible conference Close is immediate, in the same 184 × 44
primary-action slot; the backend rejects active calls and connected or
unresolved customers transactionally. Finishing a customer call preserves the
reusable bridge. Future-only scheduled calls do not prevent closing an idle
bridge.

Inline conference creation preserves the entire call draft and independently
saves the conference. Return/select follows an authoritative read. Notes start
from the source clock, preserve backdated and partial input through parking and
uncertain saves, and retry the same command. Explicit date/hour/minute controls
use Zulu throughout the application. The customer brief retains daylight-aware
America/New_York 24-hour labels.

Transport advisories use source-backed overlaps and reported assignment,
distinguish intended assignment, and remain unknown for partial or stale
coverage. Starshield transitions remain advisories. No acknowledgment gate was
added to mission planning.

## Verification

| Check                                     | Result                                                                                  | Evidence                                                                                  |
| ----------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Full frontend unit suite                  | 325 files, 2,272 tests passed                                                           | [Log](frontend-unit.log)                                                                  |
| Full Operator backend suite               | 573 tests passed                                                                        | [Log](backend-operator.log)                                                               |
| Canonical static gate                     | Passed; includes 152 tooling tests, formatting, lint and internal links                 | [Log](static-gate.log)                                                                    |
| Required CI for the application candidate | All four backend shards, backend aggregate, frontend tests/build and static gate passed | [Run 40635765539](https://github.com/bcl1713/starlink-dashboard/actions/runs/40635765539) |
| Production Docker/Nginx browser journey   | Passed, no browser page errors                                                          | [Browser log](browser.log), [proof](operator-coherent-proof.json)                         |
| Customer PDF fall-back clock              | Distinct 01:00 EDT / 01:00 EST, no AM/PM                                                | [Assertion log](pdf-dst.log)                                                              |
| Scoped runtime cleanup                    | All eight acceptance projects empty; recorded processes and listeners gone              | [Audit](cleanup-audit.json), [final ownership](ownership.json)                            |

The static gate's external adsb.lol link returned HTTP 403. External
availability is advisory under the existing gate; internal links and required
stages passed.

The real browser journey used Chromium 156.0.8078.4, en-US locale and
Pacific/Honolulu timezone. It exercised reusable bridge establishment, customer
connection/leave/finish, direct calls, safe Close, source-backed Ka and combined
restriction warnings, rescheduling, repeated timeline selection with keyboard
activation, inline conference creation with an overnight call draft, parent
cancellation preserving the conference, issue/update capture, ad hoc transport
Apply, and an interrupted note save after durable commit. Retrying that note
reused the command key and created exactly one note.

Shared sections and Display Controls were opened in the browser. The drawer's
Recenter, Open and Customer preset entries were checked; existing unit contracts
cover control acknowledgment and scope. This run does not requalify physical
camera hardware or every display control end to end.

Desktop, portrait and landscape journeys have no page horizontal overflow.
Establish/Close preserves card height and relative neighboring-card placement.
The primary action stays 184 × 44. Portrait idle cards remain 411 px tall
through establishment; landscape idle cards remain 379 px tall. Browser
auto-scrolling can change viewport coordinates, so neighboring placement is
compared relative to the target card. See the [geometry log](browser.log).

## Rendered evidence and approved reference

The sanitized reference was run locally from immutable reference commit
`ab344b936feb6fa108659a6e3b2275ee76613df6`, prototype
`9ca6297844240eaad86ecdc27e541e01e2e721ef`. Its three dist-file checksums
passed. Comparison was qualitative, using representative states at matching
viewports. The app follows the approved timeline → conference → call
organization, combined establishment, independent customers, fixed primary slot,
and compact phone chronology. It retains the repository's typography, buttons
and theme. Reference fixture content and application fixture content differ.

| View                | Application                                                                                                                | Reference                            |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Desktop 1920 × 1080 | [Operations](operations-1920x1080.png), [initial](operations-initial-1920x1080.png), [busy](operations-busy-1920x1080.png) | [Reference](reference-1920x1080.png) |
| Portrait 390 × 844  | [Operations](operations-390x844.png)                                                                                       | [Reference](reference-390x844.png)   |
| Landscape 844 × 390 | [Operations](operations-844x390.png)                                                                                       | [Reference](reference-844x390.png)   |

Additional captures: [Transport](transport-1920x1080.png),
[Issues](issues-1920x1080.png), [Notes](notes-1920x1080.png),
[History](history-1920x1080.png),
[Display Controls](display-controls-1920x1080.png).

## Review follow-through

The
[first review checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/428#issuecomment-6460518405)
identified partial Follow-Up clearing, oversized Ka duration rendering, and
workspace note-time/retained-backdate integration. All have regression coverage.
The
[second checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/428#issuecomment-6460712239)
confirmed those fixes and identified repeated timeline selection. That now
refocuses on each selection and is covered by unit and real-browser checks.

A separate whole-branch review found missing live-intent guards on restore/join,
partial coverage incorrectly becoming clear, and a browser-clock note default.
These were corrected and re-reviewed without further important findings at
`720e9ab4`; subsequent layout and historical-selection adjustments passed the
final full suite and production journey above.

## Reproduction and limits

The runner
[tools/acceptance/operator-coherent/run.py](../../../tools/acceptance/operator-coherent/run.py)
archives a clean candidate, builds the production images, starts a private
Compose project, and traverses real Nginx and backend APIs. Synthetic raw KML,
RF catalogs and controlled telemetry feed normal mission calculations and the
real journal; the source clock is live. The only browser response interception
intentionally loses a note-save response after its real durable commit. This is
synthetic acceptance, not aircraft, RF hardware, physical-device or
screen-reader certification.

```bash
OPERATOR_COHERENT_CHROMIUM=/path/to/chromium \
timeout --kill-after=20s 55m python3 tools/acceptance/operator-coherent/run.py \
  --candidate 4b7da4d89cec22a92d52f148ce4fa5ec079d7c7d \
  --project starlink-operator-425-review \
  --evidence /tmp/operator-425-review-evidence
```

[Summary](summary.json) records source-archive and image hashes, browser
identity and cleanup. [SHA256SUMS](SHA256SUMS) covers the retained package;
original full runner logs remain in `/tmp/issue425-acceptance-r8` for this
workspace. Task-owned runtime resources, private images and temporary source
trees were removed. The open-PR worktree and evidence are retained for review.
No merge or deployment was performed.
