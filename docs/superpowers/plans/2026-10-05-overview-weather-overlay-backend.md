# Overview weather backend tasks

Task appendix to the
[implementation plan](2026-10-05-overview-weather-overlay.md). Read its global
constraints, contracts, and approved spec first. B and F expand to the backend
and frontend roots defined there. Backend test commands run from B; commits run
from repository root.

## Task 1: Shared settings

**Files:** Create B/app/models/overview_weather.py and
B/app/services/overview_weather/settings.py. Test in
B/tests/unit/test_overview_weather_settings.py.

**Interfaces:** Produce strict Pydantic WeatherSettings(enabled: bool = False,
revision: int = 0), WeatherSettingsUpdate(enabled: bool), and WeatherManifest
with all ten spec fields. Produce WeatherSettingsStore(path: Path), get() ->
WeatherSettings and update(changes: dict[str, object]) -> WeatherSettings. No
provider dependencies; settings exceptions are translated by Task 3.

- [ ] **Step 1: Write failing settings tests.**

```python
def test_defaults_and_idempotent_save(tmp_path):
    store = WeatherSettingsStore(tmp_path / "overview-weather.json")
    assert store.get() == WeatherSettings(enabled=False, revision=0)
    assert store.update({"enabled": True}).revision == 1
    assert store.update({"enabled": True}).revision == 1
    assert store.update({"enabled": False}).revision == 2
```

Add named cases for restart persistence; empty/unknown/null/string/integer
updates; corrupted saved data; concurrent writers; and failed fsync/replace
preserving the previous bytes, enabled value, and revision. A corrupt existing
file must fail closed rather than silently overwrite configuration.

- [ ] **Step 2: Run RED.**

```bash
uv run --with-requirements requirements.txt pytest tests/unit/test_overview_weather_settings.py -q
```

Expect failure importing the new model/store, then behavioral failures until the
implementation exists.

- [ ] **Step 3: Implement the models and settings store.**

Follow existing locked settings-store patterns: strict validation, process/file
lock, temporary sibling file, fsync, atomic replacement. Validate before
writing; only actual enabled changes advance revision. Build
ready/off/unavailable manifest variants with integral UTC milliseconds and
nullable values exactly as specified. Constructor performs no provider access.

- [ ] **Step 4: Run GREEN.** Repeat Step 2; all cases pass. Also run the
      existing tests/unit/test_config.py suite to check shared settings
      conventions.
- [ ] **Step 5: Commit.** Stage only this task's model, store, and tests.
      Commit: `feat: persist default-off Overview weather settings`.

## Task 2: Bounded HTTPS transport

**Files:** Create
`B/app/services/overview_weather/{clock.py,protocol.py,transport.py,__init__.py}`;
add direct h11 dependency in B/requirements.txt. Create
B/tests/fixtures/weather_streams.py,
B/tests/unit/test_overview_weather_protocol.py, and
B/tests/unit/test_overview_weather_transport.py.

**Interfaces:** Produce WeatherClock(utc_ms: Callable[[], int], monotonic:
Callable[[], float]) with real-clock defaults; WeatherPayload(body: bytes,
headers: Mapping[str, str]); WeatherUnavailable(retry_after_seconds: int = 30).
Resolver is async (host: str, timeout: float) -> list[str]. TlsOpener is async
(ip: str, host: str, context: SSLContext, timeout: float) -> tuple[StreamReader,
StreamWriter]. Injection changes I/O, never validation.

Produce PinnedWeatherTransport(clock: WeatherClock, resolver: Resolver | None =
None, opener: TlsOpener | None = None), with fetch(url: str, max_bytes: int,
expected_type: str, deadline: float, \*, before_attempt: Callable[[], None]) ->
WeatherPayload (async). Produce exchange_http(reader: StreamReader, writer:
StreamWriter, host: str, path: str, max_bytes: int, expected_type: str,
deadline: float, clock: WeatherClock) -> WeatherPayload (async) in protocol.py.
Caller owns writer cleanup; protocol owns bounded HTTP framing only.

- [ ] **Step 1: Write failing transport/protocol tests.**

Use controlled numeric-IP stream fixtures with close/wait counters, raw HTTP
bytes, controllable DNS/connect/read delays, and TLS argument capture.

```python
async def test_cancel_after_open_closes_once(stream_fixture):
    task, writer = await stream_fixture.start_blocked_exchange()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert writer.close_calls == 1
    assert writer.wait_closed_calls == 1
```

Pin five-second pre-DNS/admission deadline, slow chunks without deadline resets,
multiple candidates consuming attempts, numeric dialing with original Host/SNI,
verified TLS context, all private/loopback/link-local answers rejected,
malformed host/path and redirects rejected. Test chunked decoding, conflicting
framing, header bytes >32768, body bounds 131072/2097152, truncation, unexpected
status, type/encoding, and cancellation during body and bounded close. Keep
production certificate checking enabled; test certificate errors through the
injected opener.

- [ ] **Step 2: Run RED.**

```bash
uv run --with-requirements requirements.txt pytest tests/unit/test_overview_weather_protocol.py tests/unit/test_overview_weather_transport.py -q
```

Expect missing imports or unmet framing/ownership assertions.

- [ ] **Step 3: Implement transport and framing interfaces.**

Declare h11>=0.16.0,<0.17 explicitly. Reconstruct only fixed HTTPS provider
paths; validate every resolved address, dial public numeric candidates with
original hostname SNI and verified SSLContext. Call before_attempt immediately
before each actual attempt, including failed connections. Propagate one absolute
deadline through DNS, connect, drain, and all reads. Use h11 Request/Response,
Data and EndOfMessage; separately cap raw header bytes including complete
headers. Reject framing ambiguity and non-identity content encoding. Bound
decoded body bytes as they arrive. One fetch finally block closes/waits once;
cancellation cleanup gets at most one second. No global writer registry closes
them again.

- [ ] **Step 4: Run GREEN.** Repeat Step 2; all cases pass. Run black/ruff on
      the new service files and tests through the existing backend tooling.
- [ ] **Step 5: Commit.** Stage this task's files and direct dependency. Commit:
      `feat: add bounded pinned weather HTTPS transport`.

## Task 3: Acquisition service and production API

**Files:** Create
`B/app/services/overview_weather/{admission.py,acquisitions.py,service.py,request.py}`
and `B/app/api/overview_weather.py`. Modify B/main.py router, `startup_event`, and
shutdown_event anchors and F/nginx.conf API locations. Remove
B/app/api/weather.py, B/app/services/weather_radar.py, and their obsolete unit
tests. Create `B/tests/unit/test_overview_weather_{acquisitions,service,api}.py`
and B/tests/integration/test_overview_weather_lifecycle.py. Reuse Task 2 stream
fixtures.

**Interfaces:** Consume Task 1 store/models and Task 2 clock/transport/payload.
Produce WeatherAdmission(clock: WeatherClock), take_attempt() -> None, and
admit(deadline: float) -> AsyncContextManager[None], with four active/32 pending
unique exchanges. Produce WeatherAcquisitionPool(transport:
PinnedWeatherTransport, admission: WeatherAdmission, clock: WeatherClock), with
acquire(key: tuple[str, int, int, int, int], url: str, max_bytes: int,
expected_type: str, ttl_seconds: float, validate: Callable[[bytes], None]) ->
WeatherPayload (async), invalidate() -> None (async), and aclose() -> None
(async). Metadata uses a separate singleton key.

Produce WeatherService(store: WeatherSettingsStore, pool:
WeatherAcquisitionPool, clock: WeatherClock) with async read_frame() ->
WeatherManifest, radar_tile(frame: int, z: int, x: int, y: int) ->
WeatherPayload, coverage_tile(coverage: int, z: int, x: int, y: int) ->
WeatherPayload, settings_changed(settings: WeatherSettings) -> None, and
aclose() -> None. Produce await_weather_request(request: Request, operation:
Callable[[], Awaitable[T]]) -> T (async) in request.py. It raises a local
WeatherRequestDisconnected exception on actual disconnect; outer cancellation
propagates. The API discards disconnected responses without exposing internals.

- [ ] **Step 1: Write failing pool, service, API, and lifecycle tests.**

```python
async def test_route_disconnect_keeps_sibling_and_disable_closes_once(asgi_pair):
    await asgi_pair.start_same_tile_requests()
    await asgi_pair.disconnect_first()  # actual http.disconnect receive event
    assert asgi_pair.writer.close_calls == 0
    assert asgi_pair.second_pending
    response = await asgi_pair.put_settings(enabled=False)
    assert response.status_code == 200
    assert asgi_pair.writer.close_calls == 1
    assert asgi_pair.writer.wait_closed_calls == 1
    await asgi_pair.shutdown_twice()
    assert asgi_pair.writer.close_calls == 1
```

Define asgi_pair against a real router/app lifespan, production pool/transport,
and injected Task 2 streams. Additional tests: default
off/settings/Configuration cause zero attempts; last lease cancellation;
shutdown/completion race and watcher cleanup; 91st rolling-minute attempt
rejected; 5th active and 33rd pending admission bounded; failed attempts
counted; shared acquisitions; cache <=48 PNGs and <=67108864 bytes; invalid
metadata/PNG not cached; cooldown 30/300 seconds; no immediate retry; disabled
route has zero cache-body/provider access.

Pin radar.past-only selection, 60-second future tolerance, no frame regression,
age >=3600000 removal even from cached metadata, unsafe provider paths,
512-square signature/IHDR, two admitted frames, one coverage token, and UTC
midnight invalidating old coverage/cache entries. API tests cover strict saves,
failed saves, late older revisions, coords 400, unknown/expired token 404,
disabled 409, sanitized unavailable 503/Retry-After, no-store and PNG headers,
legacy route 404, and weather construction failure preserving core health.

- [ ] **Step 2: Run RED.**

```bash
uv run --with-requirements requirements.txt pytest tests/unit/test_overview_weather_acquisitions.py tests/unit/test_overview_weather_service.py tests/unit/test_overview_weather_api.py tests/integration/test_overview_weather_lifecycle.py -q
```

Expect missing interfaces, then unmet lifecycle/API assertions.

- [ ] **Step 3: Implement budgets, leases, service, request guard, and
      integration.**

Acquire a shared keyed task through a subscriber lease; release in finally,
cancel/await after the last release. Start the deadline before admission.
Validate payload before success-cache publication; bound TTL/LRU bytes and
generation registries. Use rolling monotonic attempt accounting retained across
off/on. Fenced invalidate cancels/awaits tasks outside held locks; repeated
close shares completion and rejects new demand. Sanitize failures with bounded
Retry-After.

In service.py implement validate_png(body: bytes) -> None and metadata
validation with at most 32 past entries, exact provider hosts/paths, integral
nonboolean times, eligibility and no regression. Build same-origin templates,
register only current UTC-day coverage, prune expired generations before any
cached return. settings_changed fences older revisions and cancels before a
disable PUT returns.

The request guard races operation against request.receive disconnect events and
removes its watcher on every exit. Router responses are buffered; perform no
provider acquisition for settings. Instantiate optional app.state weather
service without network startup; initialization failure leaves core services
running. Add ^~ /api/overview-weather/ Nginx location before image regex
handling, using existing proxy conventions and disconnect propagation. Remove
legacy imports, router, service, and tests after new 404 regression exists; do
not widen CSP.

- [ ] **Step 4: Run GREEN.** Repeat Step 2 plus Task 1–2 suites; all cases pass.
      Production Nginx routing is additionally proved by Task 7 rather than
      mocks.
- [ ] **Step 5: Commit.** Stage only the named changes and legacy removals.
      Commit: `feat: serve revisioned Overview weather with bounded lifecycle`.
