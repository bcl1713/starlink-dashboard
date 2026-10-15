# Route-linked SIGMET production acceptance — 2026-10-15

## Result and provenance

Production acceptance passed all three browser tests on committed candidate
`536cf006a7ed50f68a37b75ca5a3efaf53c9f174`. The no-cache production images and
browser test sources used that same archive. The subsequent evidence commit
changes documentation only; it does not claim a separate image run for its SHA.
This report distinguishes deterministic controls from the dated real AWC replay;
neither establishes current live weather or target-workstation performance.

The acceptance runner archives the committed candidate once for production image
builds and browser test/config/helper sources. Both images build without cache.
Browser dependencies are reused only after matching the candidate package lock;
they are linked after Docker builds to keep the build context uncontaminated.
`candidate.json` records archive, browser-source and executable hashes, Node
version and Docker context; `images.log` records resulting image identities.

Node 22.22.2 and provisioned Chromium use actual native WebGL2 through
SwiftShader. The browser uses production Nginx and real APIs. Fixture code
substitutes source transport and a shared actual-UTC clock; it does not
intercept route-SIGMET API reads or acknowledgement/settings writes. Simulation
replay time stays separate.

## Behavior exercised

Independent Configuration and passive Overview browser contexts exercise
keyboard layer enablement, intersecting-only filtering, current notices, three
cards plus overflow, Clear and Show again, and propagation within eight seconds
of successful saves. Actual native scene observations record advisory outlines,
confirmed route spans, depth testing, geometry/material ownership and the shared
weather budget. The camera is placed into manual exploration through a real
pointer gesture and allowed to settle before notice updates; camera pose and
focus must stay unchanged.

Synthetic variants cover new, amended, cancelled and reused-series advisories;
unknown location, empty feed, stale source, original expiry, route changes,
antipodal incomplete evaluation, delayed old-source completion and current
running/completed simulation contexts. Simulation geometry uses its replay route
while weather validity uses actual UTC. Desktop 1920×1080, fullscreen and mobile
390×844 captures retain the passive cards and core map status. Configuration
owns SIGMET actions; Overview and its station inspection chooser expose none.

Two repeated hidden/offline cycles and unmount verify disposal with METAR, TAF
and radar enabled. Host visibility events are controlled in the test; browser
network offline mode is real. The native read-only budget snapshot records
encoded/decoded/GPU and slot peaks; it exposes no product UI control. A source
transport ledger verifies the two clients share one initial SIGMET acquisition.
The retained legacy aviation test covers station picking, polygon holes, both
antimeridian sides, radar coexistence, unavailable sources and disable disposal.

## Dated real source replay

The pinned raw AWC international SIGMET GeoJSON capture is retained with its
source manifest, attribution, normalization summary and normalized collection in
`test-results/route-sigmet-source/`, independently of disposable planning
scratch. Each production run also copies the complete source bundle into its
evidence folder before starting services.

- Source: `https://aviationweather.gov/api/data/isigmet?format=geojson`.
- Capture: `2026-10-15T01:25:01.524Z` (`1792027501524` UTC milliseconds).
- Raw size: 110,759 bytes; 152 source records.
- Raw SHA-256:
  `8c4c65bb33a7ffb842538f4374029cf6df03a977443aa0fd8e7bd0073a22fc37`.
- Normalization: 151 admitted features, 116 located and 35 unlocated.

The separate replay uses capture UTC for both source eligibility and route
matching, selects a route from a located advisory, and verifies the admitted
production-normalized payload and native outline/span rendering. Its JSON and
screenshot are labeled dated evidence, not current live weather. The original
manifest preserves provider/issuer attribution and unresolved completeness and
redistribution qualifications.

## Integration regressions found and fixed

1. Nginx gzip responses omitted Content-Length. The route reader reserved the
   entire encoded allowance for each unknown-length read; retained METAR/TAF
   allocations then blocked every subsequent Overview update. A successful Clear
   could remain invisible despite HTTP 200 polls. Incrementally reserved 64 KiB
   slabs now account for retained buffers and the final join, retain the hard
   response cap, and handle compressed lengths and cancellation cleanup.
2. A successful response carrying an unavailable source product was labeled
   loading because it had no transport error. Presentation now honors the
   admitted unavailable state and shows no stale geometry.
3. A pre-aborted signal could reject before the shared helper observed an
   already-created fetch promise, causing an unhandled AbortError. The helper
   observes that promise while preserving immediate cancellation semantics.

4. Source expiry returned an unavailable snapshot with no notice-store revision.
   The browser rejected revision zero after a positive revision and retained old
   cards. Current empty unavailable/evaluating/off/no-route states now clear the
   display while preserving the monotonic acknowledgement fence and
   confirmations; older ready-state responses still cannot restore acknowledged
   notices.
5. Optional weather status blocks pushed passive cards below the desktop
   viewport. Notices now precede those optional statuses, with compact spacing
   and unchanged text size. Production assertions check all three card bounds in
   desktop and fullscreen views, and mobile screenshots explicitly scroll to
   readable cards. Intentional scrolling weather rails now contribute their
   visible container bounds to layout selection; offscreen legend content no
   longer forces a fullscreen fallback. Core overlap and clipping checks remain.

Each production fix has a failing regression recorded before its passing result.
Failed production traces and cleanup receipts remain retained; no failed run has
a PASS file. Browser tests retain the zero-unhandled-error assertion.

## Gates and ownership

Accepted evidence directory:
`test-results/route-sigmets-378840484cec/536cf006a7ed50f68a37b75ca5a3efaf53c9f174/`.
`PASS.json` was written after `cleanup.json` verified teardown. The retained
`candidate.json`, `images.log`, `proofs.json`, browser report, native snapshots,
source-request ledger, raw capture, derived normalization and screenshots
provide provenance. Archive SHA-256:
`0222405461f537d7cfee4f42000dfd7544457eb3a78df807cd934823db40ff2f`.

| Gate                                                       | Result                                                  |
| ---------------------------------------------------------- | ------------------------------------------------------- |
| Required backend regression selection                      | 343 passed                                              |
| Full frontend unit suite                                   | 218 files, 1,610 tests passed                           |
| Production build / ESLint                                  | Passed                                                  |
| Runner failure, timeout, ownership and provenance controls | 25 passed                                               |
| Changed Python Black / Ruff                                | Passed                                                  |
| Changed-file Prettier / Markdown / filename checks         | Passed                                                  |
| Production Nginx/native WebGL browser acceptance           | 3 passed in 2.6 minutes                                 |
| Dated real AWC replay                                      | 151 normalized features; native outlines/spans verified |
| Unhandled browser errors                                   | Zero                                                    |

| Successful Configuration save | Overview convergence |
| ----------------------------- | -------------------- |
| Enable                        | 4,480 ms             |
| Intersecting-only filter      | 3,469 ms             |
| Clear                         | 1,383 ms             |
| Show again                    | 4,960 ms             |

All three cards fit within the actual viewport and rail. After three consecutive
stable geometry samples, the third card ended at y=1044.1 on desktop and y=933.1
in fullscreen (1920×1080, rail bottom 1060). The scrolled mobile view was
390×844, with cards within x=23–367 and the third card ending at y=698.9; no
horizontal overflow. Screenshots were also visually reviewed. Core clock,
network and satellite overlays remain visible in their initial views.

Observed shared-budget peaks were 140,178 encoded bytes, 12,197,124 decoded
bytes, 1,615,716 GPU bytes and three slots, below the 16/32/16 MiB and four-slot
caps. Both clients shared one initial-generation SIGMET source acquisition. Two
hidden/offline cycles and unmount disposed all probed owned resources; after
unmount encoded, decoded and GPU use were zero. The shared weather budget still
recorded one slot while other shared work continued; zero total shared activity
is not asserted. Three.js singleton Sprite geometry is recorded separately as
library-owned, while its owned materials and textures remain disposal-gated.

Approved host verification in
`test-results/route-sigmet-verification/final-fix/host-final-inventory.json`
confirmed all thirteen acceptance projects and final-check ownership records
have no owned processes, listeners, containers, networks, disposable volumes or
temporary source trees. The two exact image tags from the final run were removed
and their absence verified; shared images and build cache were preserved. The
actor Docker endpoint remained `unix:///run/user/1002/docker.sock`, context
`default`. Failed-run receipts remain retained separately, without PASS files.
Unit, regression and formatting logs are retained under
`test-results/route-sigmet-verification/`.

Every check has a wall-clock timeout and forced termination grace. The runner
records a unique Compose project, reserved loopback ports, source temp
directory, private volumes, command/PID/process groups and inherited Docker
endpoint before creation. It uses the actor's rootless socket, not the root
Docker daemon. Failure, timeout and signals run scoped cleanup; Linux child
subreaping and process identity checks prevent orphaned owned browsers/workers.
Logs survive teardown. PASS is emitted only after browser proofs and verified
empty process, listener, container, network and disposable-volume inventories.

## Review follow-up

Review fixes restore GFS selection in the shared Playwright configuration while
both runners select their own test files. List-only controls verify aviation's
three tests and GFS's one production test; the GFS stack itself was not rerun.
Cleanup now records source-removal errors, verifies `source_absent: true`, and
requires that proof before PASS. Failure injection and absent/false proof
controls fail before the fix and pass afterward (25 runner controls total).

Lineage assertions identify R1 through its normalized series, require a changed
amendment digest and notice key with the same canonical bulletin key, retire the
original notice, and preserve R2–R4 identities. Cancellation removes that exact
R1 identity; reused R1 must have new validity and a different canonical
identity. Named lineage records and complete snapshots are retained.
Configuration, Overview and the separate real replay all collect page errors and
assert zero.

One rerun exposed a legacy assertion allowing only five seconds for five-second
cross-screen polling. Its trace records the next GET starting 5.026 seconds
after a successful disable save, then returning in 7.58 ms. The explicit popup
removal bound is now eight seconds; exact popup/selection/disposal assertions
remain. The failed run and timing diagnosis are retained; the fresh candidate
passed the complete suite.

The preceding acceptance-only review retained frontend 1,603-test and backend
343-test results while rerunning focused ESLint, TypeScript, Python and
formatting checks. The final presentation changes below reran the full frontend
suite; the backend and runner remain unchanged since their 343-test and
25-control gates.

## Final presentation review follow-up

Detailed reports now label provider `series` and canonical `bulletin_series`
accurately. Overview and Configuration prefer a stable canonical bulletin label,
with a deterministic provider fallback when canonical metadata is absent. Source
reports, raw bulletin text, feature order and acknowledgement identities stay
intact.

Configuration derives future and unlocated report review directly from its bound
source collection and anchored actual UTC. These reports remain separately
reviewable when no route exists or route geometry cannot be evaluated and route
metadata arrays are empty. Cancelled and expired reports remain excluded; future
and unknown reports expose no acknowledgement actions. Exact confirmed matching
entries retain the existing Clear and Show again behavior.

Seven added regression cases failed against the original production code and
passed after the fixes. Focused checks passed 36 tests; the full frontend suite
passed 1,610 tests across 218 files. Build, ESLint and changed-file formatting
passed. A fresh no-cache production run on the exact committed candidate above
passed all three browser tests, including every existing native, lineage,
propagation, layout, disposal, simulation and dated replay gate. No acceptance
gate was changed. Full fix evidence is retained in
`test-results/route-sigmet-verification/final-fix-report.md`; the final
input-equivalence receipt proves the following evidence commit changes only this
Markdown report relative to the accepted candidate.

## Limits

This acceptance does not close existing NOAA/GFS real-source validation or
hardware/target-workstation performance gaps. GFS retains its own runner and
worker/field fixture stack. Its production runner shares the aviation Playwright
configuration; both runners explicitly select their own tests. The aviation
stack does not supply GFS fields. GFS settings/API regressions remain in the
backend gate. This is geographic intersection evidence only, with altitude and
route passage-time matching explicitly unevaluated. Unknown coverage is never a
clear-route claim. Backend/unit coverage verifies acknowledgement persistence
and retention; this browser run does not restart the backend to claim restart
durability itself.

See the [operator workflow](../features/overview-weather.md) and
[API/storage contract](../api/aviation-weather.md). Whole-branch review and PR
submission remain the controller's responsibility.
