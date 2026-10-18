# Operator redesign review package

Draft design for
[issue 376](https://github.com/bcl1713/starlink-dashboard/issues/376), based on
merged `dev` commit `1a3e77d3`. Approval pending. No product UI changes.

Start with the [design alternatives and quick-action flows](design-review.md),
then inspect the [feature and action parity matrix](audit.md). Open
[mockups.html](mockups.html) locally for responsive design navigation, concept
comparison and action-editor previews. Preview commands do not call a backend.

## Recommended concept screenshots

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
