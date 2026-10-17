# Requirement ordering review correction

Product candidate: `26a43e60ba84178a73f467395672f788f53290df`. Later evidence
commits contain no product changes.

The review found that an overdue scheduled call could indefinitely occupy the
only Next requirement slot. The card now selects the earliest scheduled start at
or after the backend UTC snapshot. Earlier still-scheduled calls remain
separately visible under Attention needed. No call is silently completed or
closed. Manual snapshot refresh remains explicit; live alerts stay in #368.

## Verification

- A regression with a 1500Z overdue call and imminent 1605Z call failed against
  the earlier implementation and passes with the correction. Additional tests
  cover multiple overdue calls without a future call and equality at snapshot
  time. Unknown timing, removed/completed records and read failure guards
  remain.
- All 1,725 frontend tests across 243 files passed; ESLint and production build
  passed using Node 22.22.2. The existing bundle-size advisory remains.
- All 22 harness tests passed. The overdue fixture is appended, preserving
  existing seeded command order and idempotency keys.
- Both production browser tests passed from exact candidate Docker images.
  Synthetic preflight, leg and between-leg states at 1920×1080, 390×844 and
  844×390 explicitly assert the future call in Next requirement and the overdue
  call under Attention needed. Screenshots and `shell-proof.json` retain proof.
- Fresh full production storage failure/restart, projection and export probes
  passed. Backend product source is unchanged; original backend unit/contract
  evidence remains in the parent report.
- Acceptance containers, networks, private volumes, images, listeners and child
  groups were removed. The separately user-requested review server remains up.

`summary.json` records exact image/source identity and cleanup.
`qualification.json` contains all five passing qualification groups.
`verification.json` records local checks and review-demo refresh.

The existing user demo was refreshed in place with built frontend assets from
this candidate; its container images and IDs were retained. Synthetic overdue
calls were appended through the same idempotent seed. Existing record IDs and
versions were preserved, and a one-shot Chromium check verified both future and
overdue sections at the original review URL before closing its browser.

The earlier PR static gate failed on existing external ADS-B documentation link
timeouts. Its formatting, lint and other local static checks passed. No
unrelated link-check exclusions or timeout changes were introduced. Final-head
CI status is reported separately on the PR.
