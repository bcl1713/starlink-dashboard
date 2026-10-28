# Operator UX review corrections

Addresses
[review comment 6461501430](https://github.com/bcl1713/starlink-dashboard/pull/428#issuecomment-6461501430)
in [PR #428](https://github.com/bcl1713/starlink-dashboard/pull/428). Production
application candidate: `c7b42900f384fed490bbbcea757f7a3f61b13260`. This report
supersedes the earlier visual comparison for the current workspace; the parent
folder archives the earlier candidate.

## Corrections and rendered checks

| Review request                    | Result and verification                                                                                                                                                                                                                                                                                                                                 |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Align first conference/call cards | Shared header rows align both card tops at 392.578125 px. Forcing the conference creation button onto a wrapped row keeps both at 429.375 px.                                                                                                                                                                                                           |
| Unmistakable capture              | Explicit Schedule Call, Add Issue and Add Note in a bordered group. Create Conference remains in its lane header. All four are fully in the initial viewport at all three tested sizes.                                                                                                                                                                 |
| Call-card hierarchy               | Identity/time/state and relevant advisory precede one primary action. Call Details retains secondary actions, audit evidence and applicable recovery. Browser checks verify secondary controls start hidden, then use Reschedule and Cancel through Details. Routine absent actual times and duplicate verification readouts are omitted from the face. |
| Phone chrome                      | One chronology row retains direct selection and full timeline access. Next-work navigation uses the selected/next title. Landscape shares a row for capture and next-work navigation. The first conference title is fully visible in both orientations; one press centers and focuses the selected call action.                                         |

[Desktop initial](operations-initial-1920x1080.png) shows alignment and the
single primary call action. [Busy state](operations-busy-1920x1080.png) retains
timeline to work selection.

| View                | Current application                    | Approved reference                      |
| ------------------- | -------------------------------------- | --------------------------------------- |
| Desktop 1920 × 1080 | [Operations](operations-1920x1080.png) | [Reference](../reference-1920x1080.png) |
| Portrait 390 × 844  | [Operations](operations-390x844.png)   | [Reference](../reference-390x844.png)   |
| Landscape 844 × 390 | [Operations](operations-844x390.png)   | [Reference](../reference-844x390.png)   |

The comparison concerns workflow hierarchy and discoverability. Existing app
styling is retained; fixture content differs. Portrait shows the first
conference primary action initially. Landscape shows its identity and state,
with visible navigation to reach the selected call action. Entire conference and
call cards do not fit simultaneously in a 390-pixel-tall screen.

## Correctness and verification

Fresh review found two lifecycle edges in the new primary-action projection.
Both have regressions: resumed customer intervals supersede old interruptions,
so Restore → Customer Left leads to Finish; establishment recovery remains in
Details when Customer Left is primary, including a corrected direct transport.
Unknown current customer reports remain visible and block connection/finish.
Re-review found no further important correctness issues in this delta. That
review was static, without an independent interaction run.

- Full frontend: 325 files, **2,278 tests passed** ([log](frontend-unit.log)).
- TypeScript passed ([log](typecheck.log)); the production frontend build also
  compiled this candidate.
- Production browser: all journeys passed, no page errors ([log](browser.log),
  [proof](operator-coherent-proof.json)).
- Canonical static gate: formatting, lint, internal links and 152 tooling tests
  passed ([log](static-gate.log)). External URL availability remains advisory.
- These corrections leave backend application sources unchanged. The
  [573-test Operator suite](../backend-operator.log) and required four-shard CI
  remain the backend verification sources.

The browser still checks bridge/customer reuse, direct calls, safe Close,
source-backed overlap/reschedule, repeated timeline selection with keyboard,
retained overnight inline conference capture, parent cancellation, issue/update
and ad hoc transport capture, real note commit with lost response and same-key
retry, shared sections and Display Controls entry points. Establish/Close stays
184 × 44 with stable card height and neighbor placement. Refresh announcements
no longer insert a temporary row above the cards.

## Evidence, limits and cleanup

The exact-SHA production backend/Nginx run uses controlled raw KML, RF and
telemetry inputs, a live source clock and real calculation/journal APIs.
Chromium 156.0.8078.4 ran in en-US / Pacific/Honolulu at the three viewports.
Only the note-save response is intercepted, after real durable commit. This does
not certify aircraft/RF hardware, physical mobile devices, screen readers or
every physical display interaction. Existing acknowledgment/scope contracts
remain covered by automated suites.

[Summary](summary.json) records source/image identities and cleanup;
[ownership](ownership.json) records commands, PID/groups and private resources.
[Cleanup audit](cleanup-audit.json) retains all thirteen runners' completed
cleanup and the final empty host query for task-prefixed Docker resources and
task processes. Each runner verified its listener and children gone. Temporary
source trees and private images were removed. The open-PR worktree and evidence
remain for review. No merge or deployment occurred. [SHA256SUMS](SHA256SUMS)
covers this evidence folder.
