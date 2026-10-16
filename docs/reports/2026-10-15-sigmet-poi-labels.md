# SIGMET labels using POI callouts

Overview SIGMET labels now use the same content-sized callouts as POIs:
12px text, a compact rounded background, leader lines, shared overlap handling,
and globe occlusion. Advisory colors identify the border and leader. Native
polygon outlines, route spans, picking and acknowledgement remain unchanged.

The presentation exposes anchors only for admitted highlights on the current
attention page (at most three). The shared React callouts replace fixed-world
sprite rectangles and remove their canvas/texture allocations. Selected-only
reports use their polygon anchor; intersections retain the confirmed span
anchor. Clearing attention removes the corresponding callouts.

## Verification

- Failing regressions demonstrated the old sprite and absent advisory color.
- Focused suite: 37 tests passed. After removing the obsolete canvas mock,
  all six native highlight tests passed without canvas creation.
- Full frontend: 221 files, **1624 tests passed**. ESLint and production
  TypeScript/Vite build passed; existing bundle-size advisory remains.
- Exact production candidate: `67fb96a11836a987bf933d3aeb1633357ffbe329`.
  All **four production browser scenarios passed** in 3.8 minutes, including
  dated AWC replay, native disposal and shared attention. New assertions check
  shared callout classes, compact font/width, and page changes from three
  labels to one and back.
- Production cleanup receipt reports no containers, networks, volumes,
  processes or errors; ports are free and disposable source is removed.
- The requested live preview was checked with browser loopback access blocked.
  Route loading succeeds; three pending and one cleared sample reports remain.
  Each sample callout measured approximately 83px wide with a 12px font. The
  desktop screenshot was visually inspected for readability and overlap.

The evidence documentation commit does not claim a separate production image
run. Backend behavior is unchanged by this follow-up.

## Evidence and review

Production evidence remains in the preserved feature worktree under:

```text
test-results/route-sigmets-ea1cc1695117/67fb96a11836a987bf933d3aeb1633357ffbe329/
```

The folder retains `PASS.json`, `proofs.json`, source/image provenance, browser
logs, screenshots/traces and `cleanup.json`. Local frontend logs and the live
screenshot are retained under `test-results/sigmet-poi-labels/`.

Independent read-only review found no blocking issue in `140250ed..67fb96a1`.
One minor follow-up remains: the shared layout parser interprets a zero marker
radius as its default 17px. SIGMET callouts therefore inherit POI marker
clearance, which can displace or group labels slightly earlier. Changing that
shared layout behavior was deferred to keep this approved visual change scoped.

This branch targets `dev` and depends on open prerequisite PRs #337 and #338.
Only the explicitly requested live preview is retained. Its source and stop
instructions are recorded in the local review runtime ownership files. The
existing same-origin proxy correction is preserved. Synthetic/software-WebGL
checks do not establish target-workstation performance or current live weather.
