# Operator redesign review package

Draft design for
[issue 376](https://github.com/bcl1713/starlink-dashboard/issues/376), based on
merged `dev` commit `1a3e77d3`. Concept A is approved; the detailed
implementation plan requires separate review. No product UI changes.

[Implementation specification](../../superpowers/specs/2026-10-18-operator-workspace-implementation.md)
and
[implementation plan](../../superpowers/plans/2026-10-18-operator-workspace.md)
include the approved persistent owners, whole-system guided training, manual and
quick reference. The
[approval record](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253399573)
approves design, not product changes; the
[training clarification](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253414196)
is mandatory scope in the plan.

**Download and open [the current standalone prototype](review-v2.html).** It
opens with Start here; Start here / Help remains visible. Working-view buttons
navigate; Demo options compares or resets synthetic scenarios. Illustrated-only
controls are labeled and explain what they represent.

Read [revision 3 orientation and required guide deliverable](revision-3.md) and
[revision 2 design contracts](revision-2.md). The
[feature and action parity matrix](audit.md) remains a mandatory
implementation/acceptance checklist. Preview commands do not call a backend. The
original narrative and mockups below are retained as the first review iteration;
revision 2 supersedes their layout and ownership decisions where they differ.

## Prototype orientation

| Scenario                              | Desktop                                         | Portrait                                       | Landscape                                       |
| ------------------------------------- | ----------------------------------------------- | ---------------------------------------------- | ----------------------------------------------- |
| Start here on a standalone download   | [Desktop](v3-start-here-1920x1080.png)          | [Portrait](v3-start-here-390x844.png)          | [Landscape](v3-start-here-844x390.png)          |
| Illustrated History destination       | [Desktop](v3-illustrated-history-1920x1080.png) | [Portrait](v3-illustrated-history-390x844.png) | [Landscape](v3-illustrated-history-844x390.png) |
| Named layout / scenario reset options | [Desktop](v3-demo-options-1920x1080.png)        | [Portrait](v3-demo-options-390x844.png)        | [Landscape](v3-demo-options-844x390.png)        |

The current runner checks a copied standalone download, opens/closes Help while
editing, finds History through Tools, and parks/resumes a draft. It produces
**58 captures and 16 scenario checks**, including the revision-2 journeys below.
Those are automated prototype checks; first-time human task completion without
coaching and the full shipped Operator guide remain required acceptance work.

## Revision 2 visual comparison

All concepts use the same five connected intervals, established/preparing
bridges, next requirement/prep, overdue call, two follow-ups and three modeled
advisories.

| Concept                  | Desktop 1920×1080                    | Portrait 390×844                    |
| ------------------------ | ------------------------------------ | ----------------------------------- |
| A · Mission workspace    | [Desktop](v2-a-stress-1920x1080.png) | [Portrait](v2-a-stress-390x844.png) |
| B · Event desk           | [Desktop](v2-b-stress-1920x1080.png) | [Portrait](v2-b-stress-390x844.png) |
| C · Communications board | [Desktop](v2-c-stress-1920x1080.png) | [Portrait](v2-c-stress-390x844.png) |

### Recommended concept and lifecycle walkthrough

| Scenario                                                     | Desktop                                              | Portrait                                            | Landscape                                            |
| ------------------------------------------------------------ | ---------------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------- |
| Stress Operations                                            | [1920×1080](v2-a-stress-1920x1080.png)               | [390×844](v2-a-stress-390x844.png)                  | [844×390](v2-a-stress-844x390.png)                   |
| Busy Communications                                          | [Desktop](v2-comms-1920x1080.png)                    | [Portrait](v2-comms-390x844.png)                    | [Landscape](v2-comms-844x390.png)                    |
| Establish/verify C, join C, leave Alpha; A stays established | [Desktop](v2-comms-after-leave-1920x1080.png)        | [Portrait](v2-comms-after-leave-390x844.png)        | [Landscape](v2-comms-after-leave-844x390.png)        |
| Interrupt Bravo                                              | [Desktop](v2-comms-interrupted-1920x1080.png)        | [Portrait](v2-comms-interrupted-390x844.png)        | [Landscape](v2-comms-interrupted-844x390.png)        |
| Restore Bravo as new linked interval                         | [Desktop](v2-comms-restored-1920x1080.png)           | [Portrait](v2-comms-restored-390x844.png)           | [Landscape](v2-comms-restored-844x390.png)           |
| Reschedule with unknown duration                             | [Desktop](v2-call-reschedule-1920x1080.png)          | [Portrait](v2-call-reschedule-390x844.png)          | [Landscape](v2-call-reschedule-844x390.png)          |
| Applied-only move with active-call advisory                  | [Desktop](v2-transport-1920x1080.png)                | [Portrait](v2-transport-390x844.png)                | [Landscape](v2-transport-844x390.png)                |
| Valid applied-only action, no acknowledgment gate            | [Desktop](v2-transport-report-preview-1920x1080.png) | [Portrait](v2-transport-report-preview-390x844.png) | [Landscape](v2-transport-report-preview-844x390.png) |
| Issue lifecycle and mitigation controls                      | [Desktop](v2-issues-1920x1080.png)                   | [Portrait](v2-issues-390x844.png)                   | [Landscape](v2-issues-844x390.png)                   |
| Historical correction after resolve/reopen                   | [Desktop](v2-issue-correction-1920x1080.png)         | [Portrait](v2-issue-correction-390x844.png)         | [Landscape](v2-issue-correction-844x390.png)         |
| Mission chooser / record scope                               | [Desktop](v2-mission-1920x1080.png)                  | [Portrait](v2-mission-390x844.png)                  | [Landscape](v2-mission-844x390.png)                  |
| Store down / last-known events                               | [Desktop](v2-down-1920x1080.png)                     | [Portrait](v2-down-390x844.png)                     | [Landscape](v2-down-844x390.png)                     |

Timing comparison: [preflight Planned UTC](v2-planned-1920x1080.png),
[airborne Live ETA](v2-a-stress-1920x1080.png),
[airborne live timing unavailable](v2-unavailable-1920x1080.png). The
[draft/save tray](v2-drafts-1920x1080.png) distinguishes unsent input, uncertain
commands and conflicts across mission targets.

### Keyboard constraints and live update

These reserve browser-chrome and keyboard regions inside the named viewport;
they do not simulate an actual mobile OS. The preview focuses a long input,
injects a customer interruption/new urgent advisory, and retains focus/input.

| Scenario                                      | Portrait                                      | Landscape                                     |
| --------------------------------------------- | --------------------------------------------- | --------------------------------------------- |
| Move with live update while typing            | [390×844](v2-keyboard-transport-390x844.png)  | [844×390](v2-keyboard-transport-844x390.png)  |
| Call with long label while typing             | [390×844](v2-keyboard-call-390x844.png)       | [844×390](v2-keyboard-call-844x390.png)       |
| Input error, Next and Save/Keep draft visible | [390×844](v2-keyboard-validation-390x844.png) | [844×390](v2-keyboard-validation-844x390.png) |

`capture-v2.cjs` originally produced 49 captures and now also covers
orientation. It exercises lifecycle separation, resolve/reopen/correction, valid
applied-only action, in-page draft parking and resumption, live-update focus
preservation, layout and 44px button heights. `preview-v2-check.json` records
results and resource ownership. Run from a mission-planner directory with
installed Playwright:

```sh
timeout --kill-after=10s 3m node /absolute/worktree/docs/design/issue-376/capture-v2.cjs
```

In-page preview draft parking is not production session recovery. Several
secondary controls display labeled navigation/semantics explanations rather than
implement the whole product. Real persistence, actual device keyboards, screen
readers, receipt/conflict handling, predictor lifecycle and time-to-action
measurements remain implementation acceptance work. No task server or container
is needed for either preview runner.

## Initial concept screenshots

| State             | Desktop 1920×1080                  | Portrait 390×844                  | Landscape 844×390                  |
| ----------------- | ---------------------------------- | --------------------------------- | ---------------------------------- |
| Normal            | [Desktop](normal-1920x1080.png)    | [Portrait](normal-390x844.png)    | [Landscape](normal-844x390.png)    |
| Busy              | [Desktop](busy-1920x1080.png)      | [Portrait](busy-390x844.png)      | [Landscape](busy-844x390.png)      |
| Uncertain save    | [Desktop](failure-1920x1080.png)   | [Portrait](failure-390x844.png)   | [Landscape](failure-844x390.png)   |
| Call editor       | [Desktop](call-1920x1080.png)      | [Portrait](call-390x844.png)      | [Landscape](call-844x390.png)      |
| Applied-only move | [Desktop](transport-1920x1080.png) | [Portrait](transport-390x844.png) | [Landscape](transport-844x390.png) |
| Issue follow-up   | [Desktop](followup-1920x1080.png)  | [Portrait](followup-390x844.png)  | [Landscape](followup-844x390.png)  |
| Observation       | [Desktop](note-1920x1080.png)      | [Portrait](note-390x844.png)      | [Landscape](note-844x390.png)      |
| Display controls  | [Desktop](display-1920x1080.png)   | [Portrait](display-390x844.png)   | [Landscape](display-844x390.png)   |

## Preview verification

`capture.cjs` opens the local HTML with installed Playwright, captures all 24
states, checks document horizontal overflow and browser script errors, and
exercises editor close → More → History at each viewport. Its context and
browser cleanup runs on completion and signals. `preview-check.json` records the
run and ownership. No server, container, network or volume is started.

To regenerate, run the script from a mission-planner directory with the existing
Playwright dependencies installed, passing the absolute script path:

```sh
timeout --kill-after=10s 2m node /absolute/worktree/docs/design/issue-376/capture.cjs
```

The previews do not establish production integration, keyboard/screen-reader
acceptance, complete draft recovery, real elapsed-time improvements, or working
record operations. Those require the approved implementation and end-to-end
acceptance described in issue 376. Existing baseline acceptance screenshots are
under `docs/reports/2026-10-18-operator-archive/review-followup/`; this package
does not relabel them as a fresh baseline run.

## Approval requested

Review the structure (A, B or C), priority order, responsive layouts and key
quick-action flows. The recommendation assumes connected customers and next-call
preparation take priority. Requested changes can be made within this isolated
design worktree. Explicit visual approval is required by issue 376 before
implementation planning or product changes; this draft does not close the issue.
