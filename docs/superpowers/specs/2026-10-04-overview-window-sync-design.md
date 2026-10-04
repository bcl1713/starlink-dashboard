# Overview cross-window updates and display controls

**Issue:** [257](https://github.com/bcl1713/starlink-dashboard/issues/257)

**Status:** Approved by the user on 2026-10-04; product implementation has not
started. Implementation-plan review and execution-method selection are pending.

**Base:** `dev` at `c8a69d25ba1e58140424d87c644d8aacb62c9d54`, including merged
[PR 258](https://github.com/bcl1713/starlink-dashboard/pull/258).

## Intent and acceptance

An operator leaves Overview on a display and edits Configuration or Missions in
another window. Successfully saved changes must reach the existing display
without reload, navigation, or a focus change. Ordinary and native fullscreen
views must retain their camera intent and ongoing telemetry/history.
Configuration also needs controls for recentering that display and requesting
fullscreen.

The issue supplies this intent. The approved choices are: five-second
saved-state polling, explicit selection when multiple Overview windows exist,
and an honest local-click fallback when remote fullscreen is rejected.

## Investigation

See the
[initial investigation](../../reports/2026-10-04-overview-window-sync-investigation.md).
It reproduces stale clock labels in two browser pages with controlled API
responses. Production-path mission propagation remains to be reproduced during
implementation.

| Input affecting Overview                     | Existing delivery                                            | Required treatment                                                  |
| -------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------- |
| Clock labels and timezones                   | Mount/focus reads; local invalidation after saves/activation | Periodic confirmed-state reads in Overview                          |
| History display window                       | Settings have no polling; history bundle already polls       | Refresh settings and keep settings/bundle interpretation consistent |
| Link enable settings                         | Five-second polling stops in background                      | Continue refresh without requiring Overview focus                   |
| Active route list and geometry               | No polling; mission hooks invalidate clocks locally          | Refresh list and currently observed route detail                    |
| Mission-generated arrivals, POIs, and labels | Five-second background polling                               | Retain cadence and verify every affected mission edit               |
| Status, GPS availability, active X-band link | One-second background polling                                | Preserve cadence and existing error/freshness behavior              |
| Configured satellites                        | Mount/focus reads                                            | Refresh while Overview is mounted                                   |
| Camera-follow preference                     | Browser-local storage events                                 | Preserve browser-local semantics and manual exploration behavior    |

Audit mission activation, switching, deactivation, active-leg edits, route
changes, timeline recalculation, and Configuration saves against this table
during delivery. Failed mutations must not broadcast or display unsaved drafts
as confirmed state.

## Alternatives

1. **Recommended: saved-state polling plus a display command channel.** Existing
   APIs remain the authority for settings and mission state. A small same-origin
   channel handles ephemeral display presence, commands, and acknowledgments.
   Polling also catches changes made by another browser and recovers missed
   events.
2. **Mutation notifications plus polling fallback.** Publish successful-save
   hints to other query clients. This reduces average propagation delay but adds
   mutation bookkeeping and cancellation races; the issue does not require
   subsecond saves.
3. **Server-pushed state and commands.** SSE/WebSocket infrastructure adds
   backend lifecycle and deployment work beyond the existing REST delivery
   requirement.

## Saved-state refresh

Overview opts into a five-second background refresh for clocks, history
settings, link settings, satellites, the route list, and its enabled
route-detail query. Implement this through scoped query observer options or a
single scoped coordinator; the implementation plan must choose one owner for
each query's polling. Do not duplicate existing status, arrival, active-link, or
history polling.

Refresh on network recovery and foreground return as well. A focus change is an
additional catch-up opportunity, never a prerequisite. Query scheduling must not
depend on React Query's focused-window state. Clean up observers/listeners when
Overview unmounts and avoid overlapping requests for the same query.

For two visible windows in the same browser context, the target bound is one
five-second interval plus API response and rendering time. Browser acceptance
uses controlled responses and an eight-second ceiling measured from a successful
save response. Record actual timings. Fully suspended browser/OS windows cannot
promise a wall-clock bound; they catch up on resumption and the docs must say
so.

Use only successful API responses as saved data. Cancel or ignore obsolete reads
when a newer confirmed save or route identity supersedes them; preserve existing
link-settings cancellation guarantees. Add AbortSignal support only where
needed. Do not introduce shared settings payloads in local storage or the
command channel.

Settings refreshes must preserve the mounted Canvas, charts, camera intent,
follow preference, and retained history. A route change may trigger the existing
automatic camera framing behavior; a manually explored view must retain its
intent. A saved history-window change intentionally changes the displayed
window, using existing retention and gap rules rather than clearing all history.
Do not label cached pre-change bundles as belonging to the new window.

Failures retain last confirmed settings according to existing error UI; unsaved
Configuration drafts are never imported into Overview. Automatic refetch must
not overwrite an operator's in-progress clock form. Mission-derived data remains
subject to existing freshness/unavailable states. This change establishes
eventual convergence across endpoints; it does not create an atomic backend
snapshot API.

## Display presence and commands

Use a versioned BroadcastChannel on the same origin/browser storage partition.
Each mounted Overview gets an ephemeral identifier. Discover responses and a
five-second heartbeat report identifier, actual fullscreen state, and supported
actions. Remove peers after fifteen seconds without a heartbeat; unmount sends a
best-effort departure message and closes listeners/channel resources.

Configuration shows an Overview display card. With one peer it selects that
peer. With multiple peers it requires explicit selection and labels peers
consistently within the session. With none it shows clear feedback and an **Open
Overview** action that opens a separate window on a user click, retaining
Configuration. It must report blocked popups rather than claiming a window was
opened.

Messages have a closed schema: version, type, sender, target, request ID, and
the specific action/status fields. Reject unknown types, malformed messages, and
commands targeted at another peer. A received command is never rebroadcast.
Remember a bounded set of recent request IDs so duplicate delivery cannot
execute an action twice. Channel failure disables remote controls with clear
feedback; ordinary saved-state synchronization continues through REST polling.

**Recenter view** targets the selected Overview and invokes the same `onReset`
behavior as its existing map control. It preserves fullscreen and live data and
restores the current follow/automatic camera behavior. Report success only after
the target accepts the action; do not claim its animation has already settled.

Commands expire after three seconds without an acknowledgment. Delayed command
messages include an expiry and must not execute after that deadline. Late
replies cannot replace feedback for a newer command. If the window disappears,
selection and controls become unavailable without silently choosing another
display.

## Fullscreen behavior

Configuration's **Fullscreen** action asks the selected Overview to enter native
fullscreen. It never fullscreens Configuration or navigates either window. Show
state derived from the target's `document.fullscreenElement` and
`fullscreenchange`; sending a request is not proof of fullscreen.

The [Fullscreen API standard](https://fullscreen.spec.whatwg.org/) requires
transient activation in the relevant window. In the initial Chromium probe, a
trusted click in a same-origin controller window could not fullscreen its popup:
the request rejected with `TypeError: Permissions check failed`. A trusted click
inside the popup succeeded. Ordinary cross-window messaging cannot be assumed to
transfer that activation.

Attempt the request in the target, handle absence/rejection, and tell the
operator to click **Fullscreen** in Overview when browser policy requires local
interaction. Make that fallback easy to find in Overview and show the
controller's state change after the local click. The request has no lingering
effect after its deadline. Do not require browser policy changes, special launch
flags, or experimental permissions. Already-fullscreen peers return their
current state without another entry attempt. Escape/local exit updates
Configuration's reported state.

This is the portable supported workflow. Browser-specific remote entry can work
when the browser grants permission, but it must be tested and reported honestly.

## Verification and documentation

- Establish failing browser cases for stale clocks and mission-derived route
  context before product changes. Use two pages/windows in one context and leave
  the editing window focused throughout the propagation observation.
- Exercise real save/activation requests against an isolated backend through the
  production Nginx path. Fixtures are suitable for timing/race/failure unit and
  browser contracts, but are identified separately from production acceptance.
- Cover labels and timezone-rendered time, activation, switching, deactivation,
  active-leg changes, history/link settings, GPS state, and camera preference.
- Test ordinary/fullscreen Overview, failed saves, interrupted reads and
  recovery, slow obsolete responses, no forced remount, camera intent, and
  retained samples.
- Cover zero/one/multiple displays, closed windows, malformed/duplicate/expired
  commands, channel failure, recenter, actual fullscreen transitions, remote
  rejection/local-click fallback, and popup rejection.
- Preserve existing globe, camera, route, arrival, history, and fullscreen
  browser regressions. Run appropriate frontend/backend/static gates after
  changes.
- Use a task-specific Docker acceptance project and the actor's configured
  daemon; preserve DOCKER_HOST/context and proxy/CA trust. Record candidate SHA,
  timings, screenshots, API responses, and cleanup evidence.
- Update `docs/features/overview.md` and relevant Configuration/operator
  guidance with save propagation delay, display selection, and fullscreen
  interaction.

## Branch lifecycle

Worktree: `/tmp/starlink-257`; branch: `feat/257-overview-window-sync`. It began
at `f71a7034955bbbd8805d3310ae92af4e86581383` while PR 258 was open. After
GitHub confirmed PR 258 merged, `git rebase origin/dev` moved it onto
`c8a69d25ba1e58140424d87c644d8aacb62c9d54` without conflicts. The original
checkout is independent. Refresh/rebase against `dev` again before delivery if
it advances.

The user approved this written design on 2026-10-04. Complete the implementation
plan review and execution-method gate next. Design approval does not claim
feature acceptance or authorize a merge or deployment.
