# Production Overview weather acceptance

Run from the feature worktree with a clean tracked candidate:

```sh
tools/acceptance/overview-weather/run.sh --check
WEATHER_ACCEPTANCE_CAPTURE_DIR=/absolute/path/to/immutable/capture \
  tools/acceptance/overview-weather/run.sh "$(git rev-parse HEAD)"
```

The runner validates an exact committed HEAD, archives tracked source, builds
production frontend/backend images, starts real Nginx and `main.app` lifespan,
and tests only loopback ports 15278/18278. It preserves the actor's configured
Docker socket/context and proxy settings. Named volumes and containers belong to
the `starlink-144-weather` Compose project. Existing resources cause refusal;
the exit trap removes only resources started by this run and its archive.

Provider DNS resolves to a validated public address; a synthetic TLS stream
returns real raw HTTP and geographic PNGs. Production URL, address/TLS policy,
framing, deadlines, admission, PNG validation, API routes, and settings remain
active. The test launcher also supplies a normalized alternate-source adapter
fixture and an advancing historical weather clock for explicitly labeled
saved-capture replay. Production camera selection, paired loading, budgets,
shader and freshness checks remain active. No production test endpoint or
validation bypass exists. Fixture controls live in an isolated JSON file mounted
under `/control`; tests update it atomically.

The browser uses the existing React reconciler DevTools boundary to observe
actual Three resources and read rendered GPU pixels at independently selected
landmarks. It verifies passive two-window Configuration changes, default-off
traffic, complete 2048 atlases, geographic orientation, day/night visibility,
fullscreen/mobile behavior, original canvas identity, resource release, and
telemetry continuity. The five-minute refresh uses real clocks and no reload.
Actual Nginx disconnect tests verify coalesced metadata/PNG sibling survival and
exact-once closure on global disable. Unit suites cover the shorter/longer time
boundaries, midnight, malformed provider input, ownership races, and limits.

Set `WEATHER_ACCEPTANCE_OUTPUT_DIR` to a task-owned ignored directory to retain
screenshots, trace failures, pixel/resource evidence, provider event counts,
container logs, image IDs, source SHA, and cleanup proof. Any tracked source
change requires a new candidate run. No external RainViewer traffic is sent.

Issue #288 acceptance adds actual higher-zoom acquisition, geographic
detail-only storm pixels, conservative missing masks, native touch zoom,
populated route/POI views, four fixed opacity comparisons and normalized
source/capability parsing. It defaults to 1920-by-1080 desktop; fullscreen and
mobile views are explicit. Saved capture replay requires immutable
`capture.json` and PNGs from the source comparison, mounted read-only by
`WEATHER_ACCEPTANCE_CAPTURE_DIR`. Replay retains original observation timestamps
and hashes. Its weather UTC advances from the recorded capture epoch, separately
from live synthetic fixture status; bounded recorded regional demand goes
through production owners rather than injected textures or a replacement shader.
Native camera selection is tested separately.

Coverage-edge checks use actual XYZ boundaries and antimeridian neighbors,
including partial fades and an unavailable neighbor. The probe corrects pixel
rounding using the sampled geographic ray and inspects the coverage output with
radar opacity temporarily zero; textures and the production shader stay intact.

For focused development checks, set `WEATHER_ACCEPTANCE_GREP` to a Playwright
name pattern. Leave it unset for final acceptance. Record this distinction in
evidence; filtered runs do not satisfy the full delivery gate. The provider's
rolling budgets remain shared across tests, so source-switch scenarios wait for
the real allowance instead of resetting it.
