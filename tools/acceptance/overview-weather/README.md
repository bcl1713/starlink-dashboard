# Production Overview weather acceptance

Run from the feature worktree with a clean tracked candidate:

```sh
tools/acceptance/overview-weather/run.sh --check
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
active. Only the resolver and stream opener are injected by the test launcher.
No production test endpoint or validation bypass exists. Fixture controls live
in an isolated JSON file mounted under `/control`; tests update it atomically.

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
