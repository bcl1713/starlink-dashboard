# Full-review corrections for Operator 425

Addresses
[review comment 6462224267](https://github.com/bcl1713/starlink-dashboard/pull/428#issuecomment-6462224267)
in PR #428. Production candidate: `33903dd748d2342ba58cd1cf68e32b8ad2811744`.
This report covers the latest workspace;
[earlier UX evidence](../review-6461501430/README.md) remains archived.

## Findings and verification

| Finding                                               | Correction and evidence                                                                                                                                                                                                                                                                                                 |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Inline conference creation during pending parent save | Inline entry and its handler use the save guard. Newer call edits retained during an accepted create are bound to that call ID and receipt version, preserving optimistic concurrency. Accepted-but-unreadable parent saves remain blocked and expose reconciliation.                                                   |
| Scrolled Issues panel covers capture                  | Follow-ups remain in normal document flow. The browser scrolls Issues to the bottom, hit-tests the center of Schedule Call, Add Issue and Add Note, then opens and discards each actual editor. [Scrolled capture](issues-scrolled-1920x1080.png).                                                                      |
| Raw occurrence/precision on normal cards              | Notes/History show readable YYYY-MM-DD HH:mm Zulu or Occurrence time unknown. Timestamp Details retains the original ISO value, including fractional precision, and historical precision. Known, unknown and midnight cases have component regressions. [Notes](notes-1920x1080.png), [History](history-1920x1080.png). |

The parent-save regression covers both an unchanged parent and edits made while
its create is pending. With no edits, the accepted draft retires and reopening
the saved call leads to an update. With newer edits, the retained draft becomes
an update of the accepted call. A lost response keeps inline entry blocked; an
accepted receipt with a failed current read exposes reconciliation before
continuing. These cases failed before the corresponding fixes and pass now.

The real production browser holds the response after a durable call commit,
edits Party while waiting, and verifies inline entry is disabled. After the
receipt/current read, it creates a conference, returns to the retained call,
saves, and reads exactly one call with the new Party and intended conference.
The accepted receipt supplies the concurrency base; a newer authoritative
version still requires existing conflict review.

## Results and retained evidence

- Full frontend: **326 files / 2,285 tests passed** ([log](frontend-unit.log)).
- TypeScript and production frontend build passed ([type check](typecheck.log)).
- Canonical static gate passed, including **152 tooling tests**, lint,
  formatting and internal links ([log](static-gate.log)). External URL checks
  remain advisory.
- Real production Docker/Nginx browser acceptance passed, no page errors
  ([log](browser.log), [proof](operator-coherent-proof.json)).
- Fresh static review confirmed the retained-call rebase and unreadable-save
  gate, with no further important findings in that change. The reviewer did not
  independently run the app.

The earlier bridge/direct workflows, independent customer intervals,
transactional Close, same-key note retry, inline overnight capture,
source-backed advisories, repeated timeline navigation and shared display
controls were rerun. Desktop card-top alignment, including wrapping, and fixed
Establish/Close geometry still pass. Portrait/landscape retain initial-screen
capture and single-press next-work navigation.

| View                | Current application                                                                                                        |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Desktop             | [Initial](operations-initial-1920x1080.png), [busy](operations-busy-1920x1080.png), [Operations](operations-1920x1080.png) |
| Portrait 390 × 844  | [Operations](operations-390x844.png)                                                                                       |
| Landscape 844 × 390 | [Operations](operations-844x390.png)                                                                                       |

## Scope and cleanup

The exact-SHA images use synthetic raw KML, RF and telemetry, a live source
clock and real production APIs/journal. Browser: Chromium 156.0.8078.4, en-US,
Pacific/Honolulu. The held call response and intentionally lost note response
follow real durable commits. This does not qualify aircraft/RF hardware,
physical mobile devices, screen readers or every physical display interaction.
Backend application sources are unchanged by these review corrections.

[Summary](summary.json) contains source/image identities;
[ownership](ownership.json) records scoped commands, PID/groups and resources.
[Cleanup](cleanup-audit.json) retains fourteen runners' completed teardown and
the final empty host query for task resources/processes. Listeners and child
groups were verified gone by each owner. Private images, volumes and temporary
source trees were removed. The open-PR worktree and evidence remain for review;
no merge or deployment occurred. [SHA256SUMS](SHA256SUMS) covers this folder.
