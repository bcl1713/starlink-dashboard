# Overview ADS-B aircraft layer acceptance

Status: COMPLETE — controlled-fixture implementation acceptance. Created:
2026-10-03; execution: 2026-10-04–05 UTC. Physical mission-display GPU
acceptance and production rollout remain pending.

Issue [244](https://github.com/bcl1713/starlink-dashboard/issues/244) was
implemented on `feat/244-overview-adsb` in `/tmp/starlink-244`, isolated from
the actor's checkout. Base: `913175dc0e19a349a9d724d1e7efcb32f1489099`.
Production candidate: `e59a18794af5125babd8a460f5c793a69119aee0`. The later
acceptance-document commit changes no runtime inputs.

## Behavior verified

The layer is disabled by default. Configuration saves installation-wide,
revisioned mode, include/exclude hexes and callsign filters. Exact six-digit
hexes retain leading zeroes; exclusions win overlaps. Included aircraft bypass
military/callsign filtering. The table includes eligible contacts worldwide,
independently of camera, route and own-aircraft position. Failed saves retain
confirmed values and expose an error; unrelated text drafts survive refreshes.

One backend lifecycle owns acquisition: 15-second cycles, no overlap, at most
four concurrent explicit-hex lookups, source-specific backoff and Retry-After.
Traffic reads do not fetch upstream. Settings persist atomically; positions
remain ephemeral. Both browser windows poll while visible and refresh on return.
Revision guards reject obsolete settings/bundles and older position
observations.

Position age uses the original provider observation: current below 30 seconds,
stale from 30 to below 120 seconds, removed at 120 seconds. Repeated replies,
errors, retained positions and resumed tabs cannot renew an old observation.
Expired/excluded selection closes details while saved include entries remain.

Overview uses instanced glyphs, tangent track orientation, Earth
depth/visibility checks, individual included labels and read-only details with
honest unavailable values and explicit units. Stale shape/text supplements
color. Selection leaves camera intent and own-aircraft follow intact. Dragging
cannot select a marker. Keyboard, Escape, focus restoration, native fullscreen
and responsive dialogs were exercised. Screenshot review found narrow identity
wrapping and a mobile dialog covered by clock cards; both were reproduced with
browser assertions and fixed. The dialog now raises its stage only while open.

See [feature behavior](../features/overview-adsb.md),
[API contract](../api/endpoints/overview-adsb.md) and the
[approved spec](../superpowers/specs/2026-10-03-overview-adsb-aircraft-addon-design.md).

## Checks and evidence

Artifacts remain under `/tmp/starlink-244-evidence`; these absolute paths refer
to this cloud session, not repository-hosted attachments.

| Check                                               | Result                                                          |
| --------------------------------------------------- | --------------------------------------------------------------- |
| `./tools/verify backend`                            | 1,577 passed; 20 skipped; two existing warnings                 |
| `./tools/verify frontend`                           | 118 files, 925 tests passed; production build passed            |
| `./tools/verify static` with the selected full base | Formatting, lint, Markdown, links and acceptance policy passed  |
| Aircraft browser suites                             | Seven Chromium cases passed                                     |
| Existing rendered regression suites                 | All 84 cases passed across the broad run and corrected rechecks |
| Exact-SHA production path                           | Nginx/API/browser/restart acceptance passed                     |

Backend output is retained in `execution/task-7-backend-final.log` and final
frontend output in `frontend-final.log`. Backend tests use controlled httpx
provider transport, including real router/lifespan restart, 2,000 contacts,
duplicate isolation, concurrent readers and source errors. Temporarily extending
expiry from 120,000 to 121,000 ms made the real-router expiry case fail;
restoring the source returned all three acceptance cases to green.

`browser-final/` and `browser-final.log` contain aircraft checks at 1920×1080,
390×844 and 844×390, native fullscreen, two-window saves, obsolete replies,
failed saves, mission changes, freshness, selection and workload/resource
cycles. Those browser suites intercept API requests through one context-level
fixture; they exercise the real production-built frontend, not the backend
transport.

The broad existing-browser run passed 78/84. Two successful-update fixtures lost
the required orbital settings field; three old assertions matched two
independent alerts; one cold WebGL pixel readiness check timed out. Complete
fixture fields and message-specific selectors fixed the first five. All six
cases passed in isolated rechecks, including the unchanged readiness case.
Evidence is in `execution/task-7-browser-final.log`,
`traffic-regression-recheck/` and `window-regression-recheck/`. This is not
presented as one clean 84-case run.

## Workload performance and limits

The isolated measurement in `performance-isolated/` used 2,000 globally
distributed eligible aircraft plus duplicate records and 50 included identities
near the visible region, with existing route/history/links. Each mode measured
30 seconds of bounded camera motion at 1920×1080. The browser was Chromium
153.0.8010.12 on Linux, with its Desktop Chrome emulated Windows user agent.
Hardware: Intel Core i9-10900K 3.70 GHz, 20 logical CPUs. Renderer: ANGLE Vulkan
1.3 SwiftShader Device (Subzero), a software GPU.

| Measurement                  | ADS-B off |  ADS-B on |
| ---------------------------- | --------: | --------: |
| Captured frames / 30 seconds |       510 |       277 |
| Frame interval p50           |  50.10 ms | 116.60 ms |
| Frame interval p95           |  83.30 ms | 133.40 ms |
| Frame interval p99           |  99.90 ms | 166.60 ms |
| Draw calls at final capture  |        23 |        24 |
| Triangles at final capture   |    17,442 |    77,442 |
| Geometries                   |        17 |        19 |
| Textures                     |         3 |         3 |
| Aircraft instances           |         0 |     2,000 |
| Aircraft identity DOM labels |         0 |        50 |

Every eligible instance and all 50 labels were present; the Configuration table
contained 2,000 rows plus its header. By the final capture, the aircraft had
aged into the stale batch. Three disable cycles returned geometries/textures and
labels to baseline. One immediate draw counter retained the preceding rendered
frame; later captures returned to 23 calls and 17,442 triangles.

CPU profiling identified triangle raycasts for HTML Earth occlusion. An analytic
sphere proxy, derived from the actual globe world transform, reduced those hot
triangle-intersection samples by approximately 95%; transform/near/far and rear
visibility checks remain. Stale rings use eight segments instead of twenty. The
final software-rendered workload still has visibly slow camera motion, about
nine frames per second with ADS-B enabled. This evidence does **not** establish
smooth interaction on a mission display. Check the same workload on the intended
physical GPU before rollout; no frame-time acceptance threshold was specified.

## Production path

`tools/acceptance/adsb/run.sh` archives the clean candidate SHA and builds the
repository backend/frontend Dockerfiles. Task-owned Compose project
`starlink-244` uses loopback port 15244, real Nginx, backend lifespan and
Prometheus, and isolated data volumes. The actor's Docker endpoint/context
remained `unix:///run/user/1002/docker.sock` / `default`; Docker 29.8.1,
overlayfs. Proxy and trust configuration were preserved.

A read-only test launcher substitutes httpx MockTransport only for adsb.lol
URLs. Prometheus and other clients remain real. There are no production test
endpoints or settings, and no live provider traffic was required.

`production-final/` contains the candidate SHA, image IDs, build/start/restart
logs, actual Nginx settings/traffic/history responses, two-window timings,
screenshots and WebM recordings. Timings:
`enable 5,282 ms; cached inclusion 4,510 ms; exclusion 4,008 ms; newly included civilian acquisition/render 10,168 ms`.
Cached-contact changes must converge within 5 seconds plus API time; a newly
included unknown civilian can await the next shared 15-second acquisition.

After the backend restarted with provider failure, settings were byte-for-byte
equal as JSON at revision 4 and traffic contacts were empty. All task-owned
containers, named volumes and source archives were removed; images remain for
inspection. This is isolated acceptance, not deployment.

## Review and rollout

Independent whole-branch review is the final gate; the verdict will be recorded
before handoff. Merge, deployment and provider contact were not performed.
Before live rollout, review current
[provider usage documentation](https://api.adsb.lol/docs) and retain
[adsb.lol](https://www.adsb.lol/) /
[ODbL](https://opendatacommons.org/licenses/odbl/1-0/) attribution. Multiple
backend workers or replicas need explicit acquisition coordination; this change
preserves the repository's single-worker runtime.
