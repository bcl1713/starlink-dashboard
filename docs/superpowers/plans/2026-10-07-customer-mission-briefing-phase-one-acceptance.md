# Customer Briefing Phase-One Technical and Acceptance Details

This is the required companion to the
[phase-one plan](2026-10-07-customer-mission-briefing-phase-one.md). All checks
and generated artifacts here are implementation deliverables, not claims that
planning has produced working decks or a working renderer.

## Inspected integration points

All paths use the backend/frontend roots defined in the main plan. New tests:
`tests/unit/test_trial_maps.py`, `test_trial_package.py`,
`test_trial_export_endpoint.py`, frontend
`src/components/missions/ExportDialog.test.tsx`; extend
`src/services/export-import.test.ts` and backend `tests/unit/test_config.py`.

- `app/mission/package/__main__.py`: per-leg exports, combined CSV and combined
  PPTX each call `_load_export_timeline`; it rebuilds then falls back to
  storage.
- `app/mission/timeline_service.py::build_mission_timeline` calls
  `publish_mission_pois`. Use
  `timeline_preparation.py::prepare_mission_timeline` instead: it returns
  effective spliced route, projector, events and timeline without publishing.
  Keep its legacy normalization behavior on private copies.
- `exporter/pptx_builder.py::_get_footer_metadata` and
  `exporter/__main__.py::_cover_metadata_line` reload parent storage.
  `_generate_route_map` also reads managers. Snapshot adapters must cover these.
- `replay_state.py`, `state.py`, `call_availability.py` preserve distinct
  safety, degradation and offline semantics. Trial classification must be
  separate.
- `timeline_builder/aar.py` resolves absolute/T-plus overrides and manual track
  projections; `satellites/rules.py` owns SOF timing. AR start/end events alone
  omit window identity; retain configured source IDs beside resolved periods.
- Overview scene assets/components exist, but no export scene or backend browser
  runtime does. Production backend Docker has Python/curl, not Chromium/Node.
  Existing acceptance browser infrastructure is not a deployed export renderer.
- ZIP API returns StreamingResponse; `exportImportApi.exportMission` currently
  returns Blob only, and ExportDialog announces unconditional success.

## Projection decisions for Task 2

`SourceRecord` is an immutable export DTO: source ID, leg ID, optional
transport, source type, original start/end or instant in UTC, reason, immutable
metadata, and source revision/digest. Preserve saved
outage/track/window/transition IDs; for generated events use deterministic
leg/type/time/content IDs, explicitly labeled derived identities. Preserve
original records before clipping/splitting. Canonical events allow
reconstruction of raw transport conditions lost by
`normalize_call_availability_timeline`; do not classify its call-posture labels.

`UsabilityDecision` contains `value: Literal['Up', 'Down', '?']`, rule ID,
source IDs and table-only limitation. `ClockLabels` contains `et`, `zulu` and
`relative`. `TrialInterval` keeps UTC boundaries and full source IDs. Table/map
labels use leg-local window numbers assigned to the complete display partition
before filtering; skipped numbers are intentional. Maps locate relevant window
starts on the effective timed route; unmappable windows stay linked in text.

Document and test this initial classifier against `replay_state.py`,
`timeline_builder/events.py`, and `call_availability.py`:

| Evidence for this transport within this interval                                 | Trial lane | Required interpretation                                                       |
| -------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------- |
| Available, no contradictory independent evidence                                 | Up         | Nominal transport usability; preserve material limitation text                |
| Offline, including configured Ka/Ku outage                                       | Down       | Independently unavailable; retain configured outage ID/reason                 |
| Ka `ka_no_coverage`, generated coverage-exit/gap until coverage returns          | Down       | Reducer uses degraded but the source establishes no coverage                  |
| X event `line_of_sight_blocked` / `elevation_below_min`                          | Down       | Existing geometry establishes blockage below configured minimum               |
| Pure X-Ku concurrency warning, without other X degradation/blockage              | Up         | Existing normalization treats X as usable; table explains concurrency limit   |
| X transition buffer, manual AR-track degradation, X-AAR/other azimuth conflict   | ?          | Degraded warning alone does not establish either usable service or shutdown   |
| Ka transition warning without explicit independent usability evidence            | ?          | Keep transition/coordination cause visible; no invented outage                |
| Missing state, missing coverage/geometry prerequisites, unrecognized degradation | ?          | State defaults cannot establish verified availability when inputs are missing |

Independent proven unavailability takes precedence over usability/unknown
warnings; retain all causes. Pure X-Ku is Up only when no blocking/unknown X
condition coexists. A recognized usable limitation can be Up only with a tested
source-semantic rule; do not treat every warning as either usable or Down.
Cached timelines use known source reasons/metadata only when unambiguous;
otherwise `?`. Retain original cached timestamps; never blindly shift absolute
outages. Trial bounds/T-zero come from the captured effective route and current
planned departure; stale or uncovered predictions become uncertain with their
original data basis in the appendix. Both builders receive the same copied cache
and current planned metadata. Stale fallback cannot imply verified current
Nominal posture. Test combined known Down, known Up and unknown conditions.

Count only classified Up lanes. For any `?`, overall posture is neutral “Posture
uncertain”, with known usable transports and unresolved limitations. Zero known
Up plus unknown is not a total outage. All three independently Down is the only
“Communications unavailable” case. Preserve prediction caveat. Transport mapping
is Ka → Commercial Ka, Ku → Starshield, X → X-Band MILSATCOM; never reuse the
legacy display order or critical-count label for the trial.

SOF uses `ConstraintConfig.takeoff_buffer_minutes` and `landing_buffer_minutes`,
currently 15 each, at effective takeoff/landing. Resolve AR via
`resolve_aar_windows` on the prepared route/projector. Manual AR spans use the
same projected earliest/latest timestamps and selected-splice applicability as
`prepare_mission_timeline`; preserve track IDs. Missing/unresolved windows get
notes rather than timed inventions. Bounds missing entirely require a clear
leg-specific incomplete-data page, never an apparently quiet Nominal leg.

Primary table columns: Start (ET), End (ET), Event / impact, Communications
remaining, Overall posture / customer implication. Primary clocks include
seconds when needed to preserve exact endpoints; do not round a brief outage
away. Standard SOF-only/no-extra-window copy is exactly: “No communications
degradation or additional coordination windows identified for this leg”. Never
use that copy when unresolved data or limitations exist.

## Map feasibility and production architecture for Task 3

Planning inspection establishes reusable components and missing integration; it
does not establish working headless rendering. Complete this gate first:

1. Build a dedicated local export entry with `CityLitGlobe`, `GlobeRouteRibbon`,
   `globe-route-projection.ts`, `overview-camera-frame.ts`,
   `overview-route-hemisphere.ts`, and `solar-position.ts::sunLightPosition`.
   Reuse `/earth-day-hi.jpg` and `/city-lights-mask.png`. Extract pure camera
   framing as needed; do not mount OverviewPage or its interactive controller,
   subscriptions, Date.now clock, aircraft, traffic, weather or dashboard UI.
2. Run from a production-compatible, non-root image with a packaged browser.
   Produce 1920 x 1080 PNG at fixed pixel ratio 1; planned reference time is
   effective leg takeoff. Wait for decoded textures, compiled shaders, settled
   camera, projected labels and completed deterministic render, not a sleep.
   Report readiness errors explicitly. Two identical inputs in the same runtime
   produce identical geometry/framing and decoded pixels; record PNG hashes.
3. Prove short, polar and dateline routes, then a route without a containing
   hemisphere. Split its ordered geometry into consecutive fitting views with
   shared endpoints; depth-test against globe. No through-planet visibility
   hack. All route pieces/markers fit with crop padding and neutral styling.
   Label lighting “Planned-time illustration” with reference timestamp.
4. Preserve runtime/asset versions, timing, readiness log and PNGs. Failed
   startup/texture/context loss and slow rendering must also prove fallback and
   cleanup. If packaging or framing fails, repair it before trial integration;
   repeated fallback is not evidence of successful overview rendering.

**Create frontend files:** `mission-export.html`,
`vite.mission-export.config.ts`, `src/mission-export/main.tsx`, `scene.tsx`,
`protocol.ts`, `framing.ts`, and `render.mjs`. Build script
`build:mission-export` uses that separate Vite entry; output is
`dist-mission-export/`. Add that directory to root `.gitignore`. Add
`src/mission-export/framing.test.ts` and `tests/e2e/mission-export-map.spec.ts`
with a dedicated Playwright config.

`protocol.ts` defines `MissionMapInput`: schema version, leg ID, effective route
points/times, reference UTC, neutral numbered markers and framing version. Scene
reports a ready/error result with input digest and framing. The Python wrapper
passes JSON via private stdin/file, launches request-owned Node child
`render.mjs` and receives PNGs/status. Node uses the locked Playwright core and
packaged Chromium, a private loopback static listener serving only bundled scene
assets, and a fresh browser/context. No request to the live dashboard or
external screenshot service. Close listener/context/browser, terminate/reap
process group on timeout, and delete private payload/PNG paths on
success/failure/cancellation.

**Production packaging:** Keep backend Dockerfile location but change only the
backend build context to repository root in `docker-compose.yml` and the backend
matrix entry in `.github/workflows/publish-ghcr.yml`. Update backend COPY paths.
Use a Node builder to `npm ci` from frontend lockfile and build export assets;
copy scene assets, Node runtime and locked `playwright-core` into the backend
runtime. Package its corresponding Chromium and OS libraries at image build,
never download at export. Match builder/runtime OS ABI and grant appuser access.
Keep Python runtime, health checks, labels and Nginx route unchanged. Add root
`.dockerignore` allowing only explicit build inputs and excluding `.git`,
`.worktrees`, data, evidence, env/credentials and dependency caches. Review
image size/build duration and all existing COPY paths. GFS keeps its current
context. Do not broaden acceptance authority or add build fields its parser
rejects.

Request cache key includes effective route geometry/timing, adjusted departure,
leg identity, reference UTC, trial availability/markers, asset and renderer
versions, resolution/framing. No persistent slide cache. One 60-second monotonic
budget covers all extra views/legs including browser startup; exhausted budget
skips further browser work. Reuse snapshot-compatible legacy map bytes only if
neutral and suitable; otherwise call a trial-only neutral style mode of
`exporter/__main__.py::_generate_route_map` through snapshot views. Keep legacy
rendering defaults unchanged. Use “Overview map unavailable — static route
fallback”; missing route/all renderers failing uses “Route map unavailable” with
leg endpoints and reason. Bound the entire fallback stage to 10 seconds, reuse
already generated legacy map inputs where possible, and include it in export
timing; never deliver a blank slide or suppress the warning.

## Representative fixture matrix

Create `tests/fixtures/customer_briefing/` with committed mission, route and
source JSON/KML, plus expected interval/source/clock JSON. Fixtures use fixed
UTC instants, IDs and revisions, not wall-clock time or live satellite feeds.
Expose them through `tests/unit/customer_briefing_fixtures.py`. Production
acceptance imports fixture missions using normal API routes into private data.

| ID  | Fixture inputs                                                                                      | Assertions and representative pages                                                       |
| --- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| F01 | 2026-10-07 08:00–14:00Z, all three usable; long quiet leg                                           | EDT 04:00–10:00; only SOF 04:00–04:15 and 09:45–10:00 table rows; quiet-leg copy          |
| F02 | F01; Ka Down 08:10–12:15Z; X Down 09:30–11:00Z; SOF splits first period                             | Ka-only 04:10–05:30, Ka+X 05:30–07:00, Ka-only 07:00–08:15 ET; first span splits at 04:15 |
| F03 | 2-hour leg; touching outages and a nested 30-second three-Down period                               | No false overlap at touching endpoints; 30-second red window/callout; exact seconds       |
| F04 | 2026-10-07 08:00–08:20Z; available transports; overlapping SOF 08:05–08:15Z and AR                  | Both SOF labels retained; restricted union <=20 minutes; Nominal unaffected               |
| F05 | Waypoint AR, absolute and T+ overrides, manual AR tracks, selected feasible/unavailable splice      | Full resolved periods, track IDs, correct applicability, unresolved timing note           |
| F06 | Pure X-Ku warning, Ka gap, X blockage, transition-only and unknown cases, two Down plus unknown     | Plain Up/Down/?; limitations in table; uncertain never red or definitive total outage     |
| F07 | Midnight 2026-10-08 03:50–04:20Z; spring 2026-03-08 06:50–07:20Z; fall 2026-11-01 05:50–06:20Z      | Midnight EDT dates Oct 7/8; spring 01:50 EST→03:20 EDT; fall 01:50 EDT→01:20 EST          |
| F08 | Three legs on Oct 7/10/13; shared route IDs but different adjusted departures/events                | Each leg T-zero; no ground axis/duration; snapshot revisions agree; map keys differ       |
| F09 | Dense windows, long reasons/names and many legs; short/long/polar/dateline/hemisphere-spanning maps | Pagination/minimum fonts, no occlusion/clipping, source appendix, grayscale readability   |
| F10 | Missing route/timeline/coverage/AR timing; rebuild error and stale-cache fallback                   | Explicit incomplete labels; no false quiet/Nominal assertion or fabricated timing         |
| F11 | Trial exception/invalid PPTX; browser/texture/fallback errors; shared stage deadline exceeded       | Legacy ZIP/download succeeds with warning; entire failed trial omitted; zero leaks        |

F02 needs exact non-overlapping rows, not only the three outage phases: SOF
04:00–04:10; Ka+SOF 04:10–04:15; Ka 04:15–05:30; Ka+X 05:30–07:00; Ka
07:00–08:15; landing SOF 09:45–10:00. Quiet 08:15–09:45 remains in graphics. Use
a second F02 variant with nested AR and assert added splits/aggregated causes.

Also select a suitable existing mission locally; record its source fingerprint,
reason for selection and anonymization. Do not commit customer-sensitive data.
All synthetic fixtures generate paired legacy/trial decks; representative
customer bundle includes F01, F02 with AR, F06, F07, F08, F09 and F10/F11
outcomes.

## Verification and evidence for Tasks 4–6

Create root `tools/acceptance/customer-briefing/run.sh`, `generate.py`,
`inspect_pptx.py`, `render_decks.py`, and `journey.mjs`, with runner lifecycle
tests in `tools/tests/test_customer_briefing_runner.py`. Use the existing
acceptance platform's provisioned browser authority for browser acceptance.
Export renderer runtime identity is recorded separately; do not treat acceptance
browser launch as proof that the deployed renderer exists.

Focused backend commands run from `backend/starlink-location`, with relevant
new/existing test paths appended:

```bash
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
  pytest tests/unit/test_export_snapshot.py tests/unit/test_trial_projection.py \
  tests/unit/test_trial_clocks.py tests/unit/test_trial_pptx.py
```

From frontend run bounded
`npm run test:unit -- src/mission-export/framing.test.ts` and export
service/dialog tests, then `npm run build` and `npm run build:mission-export`.
Wrap each in `timeout --kill-after=10s 10m`. Final candidate uses
`timeout --kill-after=10s 30m ./tools/verify static`,
`timeout --kill-after=10s 30m ./tools/verify backend` and
`timeout --kill-after=10s 20m ./tools/verify frontend`, plus required CI at the
same SHA. Renderer/build manifest changes require fresh image builds; use a
45-minute wall limit and 10-second termination grace for acceptance/image build.

Acceptance runner takes full candidate SHA and owned evidence/task roots; starts
an isolated Compose project `starlink-dashboard-customer-briefing-<sha-prefix>`
with production Dockerfiles/Nginx, private volumes, loopback ports and explicit
flag values. Import, export and download through the real UI/API without
intercepting the export response. Check enabled/disabled packages, direct legacy
PPTX, source/import preservation, warning UI and all fixture expected results.
Record SHA/image revisions, snapshot fingerprint, browser/runtime/asset
versions, API/ZIP manifests, safe warnings, map readiness and per-stage/export
timings.

Compare legacy ZIP paths, source JSON/KML/POIs, CSV text, and PPTX XML text,
geometry, palettes, styles, relationships and media against baseline on
identical fixture inputs. Ignore only ZIP timestamps, PPTX core
creation/modification properties and explicit generated-at fields. Freeze clocks
for comparison; never ignore departures, window endpoints, source revisions,
warnings or images. Any intentional consistency fix must be identified and
reviewed explicitly.

Render actual extracted PPTX decks using pinned LibreOffice in an
acceptance-only image, with a private user profile and timeout; export PDF then
page PNGs. Preserve originals, PDFs, contact sheets, full-resolution PNGs and
grayscale primary pages. XML checks prove editable shapes/tables/embedded assets
and font sizes, but rendered inspection separately checks overlap, truncation,
page continuations, patterns, posture dominance and readable maps. Open
representative PPTX in desktop PowerPoint offline and edit a table cell/title;
record reader version and result before customer promotion. A generated PDF
alone is not proof of editable PowerPoint compatibility.

Acceptance evidence manifest maps fixture → snapshot → ZIP/deck hashes → slide
numbers → semantic assertions → rendered pages → reviewer observations. Record
customer scan tasks and time-to-answer for reduced redundancy, unavailable
periods, remaining transports and restrictions. Target a few seconds per leg;
report actual timings and feedback rather than equating unit tests with
usability.

Record PIDs/process groups, browser/session/listener handles, Compose project,
private volumes and temp paths before launch. Install EXIT/INT/TERM handlers;
close/reap scoped resources and verify after timeouts before retry. Use
configured DOCKER_HOST/context; root-socket failure is not daemon failure.
Verify owned processes/listeners and project-filtered
containers/networks/volumes are absent, using approved host inspection if
namespace isolation hides them. Preserve durable evidence/open-PR worktrees;
stop runtime resources immediately after checks.

## Review and rollout gates

Default flag is off. Planning PR contains only this plan and its companion; open
future implementation PR against `dev` and retain its worktree while open.
Return it for review and wait for authorization before implementation. Future
implementation PR needs focused tests, applicable CI gates and actual rendered
production-path evidence; specification PR CI is not implementation acceptance.
Enable the trial only in the approved evaluation environment after those gates,
then generate representative decks for the recurring customer. Disabling the
flag restores the established file set without migration. Record feedback before
promotion; no legacy replacement or phase-two worker implementation follows
without the separate explicit decisions required by the approved specifications.

Reusable boundaries are snapshot DTOs/fingerprints, pure per-leg projection, map
input/result and builder inputs. Do not add durable artifact stores, save hooks,
generation tokens/leases, scheduler recovery or assembly-only exports.
