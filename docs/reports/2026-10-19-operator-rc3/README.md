# RC3 Operator usability preview

RC2 failed human usability acceptance. This candidate changes the real UI; it
has **not** passed uncoached human evaluation. Training, curriculum and the
323-item parity matrix are unchanged and were not rerun.

## Try it

Use the existing private launcher from a fresh checkout of this PR branch:

```sh
git fetch origin feat/issue-376-operator-workspace
git worktree add --detach .worktrees/operator-rc3 origin/feat/issue-376-operator-workspace
cd .worktrees/operator-rc3
export operator_rc3_root="$(mktemp -d /tmp/operator-rc3-XXXXXX)"
timeout --kill-after=10s 20m scripts/operator-training.sh start \
  --root "$operator_rc3_root" --disposable --relay
```

`--relay` is the same managed-cloud option used for RC2; omit it when ordinary
local Docker loopback works. This reuses the existing launcher and fixture; it
does not rebuild the training system. Open the printed origin with
`/operator?workspace=1`. Select **Fictional Meridian 21**. Skip the guided
mission for this evaluation. Use the exact RC3 commit reported with the PR
handoff; record `git rev-parse HEAD` with feedback.

## Uncoached evaluation: 10–15 minutes

These are task goals, not a button-by-button lesson:

1. Schedule a voice or VTC call for a fictional customer using UTC date/time
   controls. Put it during a mission leg, check its association, then reschedule
   it. Try the explicit association override if needed.
2. Create, establish and verify a conference bridge. Associate the call with it.
   Start the call, report the customer connected and the call tested, then
   report the customer leaving and finish. Reuse the bridge for a second
   call/customer. Close and reopen the bridge if time permits.
3. From Operator, open Overview in a separate window. Recenter it and change a
   visibility setting, radar and ADS-B. Confirm the settings survive a refresh.
4. If time permits, park an unfinished call, switch views or refresh, and resume
   it. An incomplete date/time should prevent saving while preserving the draft.

Record your first hesitation, expected next action, wrong selections, errors,
and approximate time. Include browser/device, commit and screenshots if useful.
Stop where you get stuck; do not use the old guide to compensate for friction.

Stop the disposable exercise afterwards:

```sh
timeout --kill-after=10s 5m scripts/operator-training.sh stop --root "$operator_rc3_root"
```

## Scoped evidence

- [Scheduling](desktop-schedule.png), [call card](desktop-call.png),
  [mobile call](mobile-call.png), [Display tools](desktop-display.png),
  [mobile Display tools](mobile-display.png).
- [Browser workflow](browser-check.json) and
  [partial draft/recenter checks](draft-camera-check.json): one synthetic
  mission, two legs, two saved calls and one reused conference. Actual existing
  public API routers, SQLite writes and shared settings stores; no intercepted
  writes. Browser timezone was America/Los_Angeles; entry and saved association
  stayed UTC.
- The native probe used Vite, not production Docker/Nginx. Scientific feeds,
  rendered weather accuracy and actual communications hardware are outside its
  scope. The actual Overview page acknowledged Recenter; missing optional
  providers did not prevent independent operations.
- [Verification](verification.json) records focused tests, build, source hashes
  and cleanup. Full release gates and human usability approval remain pending.
