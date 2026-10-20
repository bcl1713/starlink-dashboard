# RC4 focused Operator follow-up

This incorporates the conference-lifetime and lean display-testing
clarifications. Human usability approval is still pending; no merge or cutover
is proposed.

## Try RC4

Use the
[existing launcher instructions](../2026-10-19-operator-rc3/README.md#try-it)
with the RC4 commit supplied in the PR handoff and a fresh disposable root. Use
`--relay` where it was needed for RC2/RC3. Open `/operator?workspace=1` and
reload both Operator and Overview so both windows use the candidate camera
protocol. Skip the guided mission for this follow-up.

Suggested short evaluation:

1. Create a call and a conference. Each shows a readable association; use
   **Change association** only if needed. Saved explicit associations stay
   pinned.
2. Conduct two calls on the same leg using one established conference session.
   Finishing a call leaves that session alone. Close the session at leg end.
3. Select the next leg through the existing mission controls. Reestablish the
   same saved conference, then verify it again. Its name/configuration remain;
   an old open report must not appear available across the gap.
4. Open Display tools: camera first, then visibility/presets, weather and ADS-B.
   Group shortcuts scroll directly to those existing controls. Try Follow
   aircraft on the selected Overview window. Without a fresh position, expect an
   honest unavailable acknowledgment. This action does not change the saved
   browser follow preference or other Overview windows.

Stop at the first confusing interaction and report what you expected. Do not
provision weather, traffic or orbital providers for this assessment.

## Concise control evidence matrix

| Control                        | Focused evidence reused/run                                                                                                                                                                                                                                 | Not newly observed                                                                    |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Recenter / Follow aircraft     | Existing display session, host, controller and camera tests; selected-window delivery, accepted/unsupported receipts, unchanged browser preference. Native browser: actual Overview acknowledged Recenter and reported Follow unavailable without position. | Tracking a fresh aircraft in the RC laptop's rendered scene.                          |
| Visibility / presets / history | Existing components and settings API; Operator regression and existing Overview layer fixtures pass.                                                                                                                                                        | Live metrics, ground-entry, route and orbital graphics when their sources are absent. |
| Radar                          | Operator on/off regression uses existing weather settings hook/API. Prior RC3 native settings-write proof retained.                                                                                                                                         | Precipitation rendering without source data.                                          |
| ADS-B                          | Operator on/off regression uses existing shared settings hook/API without requesting provider traffic. Existing layer fixtures retained.                                                                                                                    | Live contacts when no traffic source is available.                                    |
| Aviation overlays              | Existing settings/card reused unchanged; existing settings and Overview layer regressions pass.                                                                                                                                                             | Actual weather products without source data.                                          |

No provider instances, new provider harness, training changes, or full parity
campaign were introduced. The native smoke reused the tiny RC3 API fixture.

## Evidence

- [Conference association](conference-association.png),
  [previous-leg session](previous-session.png),
  [reestablished configuration](reestablished.png),
  [camera controls](display-controls.png).
- [Browser results](browser-check.json): two same-leg calls, one saved
  conference, explicit later-leg close/reestablishment, preserved immutable
  revision and independent customer records. The probe's fixture leg switch was
  corrected to use existing per-leg storage; the initial probe result is
  retained separately.
- [Verification](verification.json): 209 focused frontend tests, eight existing
  conference API tests, production frontend build and static checks. The first
  sandbox API run stalled and was explicitly stopped before the host run passed.
  Full mission/provider acceptance and physical-device checks were not rerun.
- [Cleanup](cleanup.json): preview processes/listeners stopped; no provider or
  Docker resources created.
