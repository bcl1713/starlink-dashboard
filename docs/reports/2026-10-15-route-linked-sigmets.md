# Route-linked SIGMET production acceptance — 2026-10-15

## Result and provenance

Production acceptance passed all three browser tests on committed candidate
`d8ac846e9e71edbfbf8ccacac5bc8daa70d9eaba`. The no-cache production images and
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
`test-results/route-sigmets-d640931bac6b/d8ac846e9e71edbfbf8ccacac5bc8daa70d9eaba/`.
`PASS.json` was written after `cleanup.json` verified teardown. The retained
`candidate.json`, `images.log`, `proofs.json`, browser report, native snapshots,
source-request ledger, raw capture, derived normalization and screenshots
provide provenance. Archive SHA-256:
`4b73858ca5cf326d693a6f5337bd36d6bfdd657ce71e3050eea4c867ebd0d06b`.

| Gate                                                       | Result                                                  |
| ---------------------------------------------------------- | ------------------------------------------------------- |
| Required backend regression selection                      | 343 passed                                              |
| Full frontend unit suite                                   | 218 files, 1,603 tests passed                           |
| Production build / ESLint                                  | Passed                                                  |
| Runner failure, timeout, ownership and provenance controls | 20 passed                                               |
| Changed Python Black / Ruff                                | Passed                                                  |
| Changed-file Prettier / Markdown / filename checks         | Passed                                                  |
| Production Nginx/native WebGL browser acceptance           | 3 passed in 2.7 minutes                                 |
| Dated real AWC replay                                      | 151 normalized features; native outlines/spans verified |
| Unhandled browser errors                                   | Zero                                                    |

| Successful Configuration save | Overview convergence |
| ----------------------------- | -------------------- |
| Enable                        | 5,663 ms             |
| Intersecting-only filter      | 3,892 ms             |
| Clear                         | 2,733 ms             |
| Show again                    | 4,832 ms             |

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
unmount GPU and encoded use were zero. The remaining 3,633,696 decoded bytes
remain in the shared weather budget; zero total decoded/cache use is not
asserted. Three.js singleton Sprite geometry is recorded separately as
library-owned, while its owned materials and textures remain disposal-gated.

Approved host verification in
`test-results/route-sigmet-verification/host-final-inventory.json` confirmed all
ten acceptance projects have no owned processes, listeners, containers,
networks, disposable volumes or temporary source trees. The actor Docker
endpoint remained `unix:///run/user/1002/docker.sock`, context `default`.
Failed-run receipts remain retained separately, without PASS files. Unit,
regression and formatting logs are retained under
`test-results/route-sigmet-verification/`.

Every check has a wall-clock timeout and forced termination grace. The runner
records a unique Compose project, reserved loopback ports, source temp
directory, private volumes, command/PID/process groups and inherited Docker
endpoint before creation. It uses the actor's rootless socket, not the root
Docker daemon. Failure, timeout and signals run scoped cleanup; Linux child
subreaping and process identity checks prevent orphaned owned browsers/workers.
Logs survive teardown. PASS is emitted only after browser proofs and verified
empty process, listener, container, network and disposable-volume inventories.

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
