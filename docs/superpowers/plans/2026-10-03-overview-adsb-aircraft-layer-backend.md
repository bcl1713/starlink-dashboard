# ADS-B Layer Backend Tasks

Read the [main plan and shared contracts](2026-10-03-overview-adsb-aircraft-layer.md)
and its approved spec first. Paths below are relative to
`backend/starlink-location/`; focused pytest commands run from that directory
with `uv run --with-requirements requirements.txt pytest`.

## Task 1: Revisioned installation settings and settings API

**Files:** Create `app/models/overview_adsb.py`,
`app/services/overview_adsb_settings.py`, `app/api/overview_adsb.py`,
`tests/unit/test_overview_adsb_settings.py`, and
`tests/integration/test_overview_adsb_settings_api.py`, and
`tests/unit/test_main_overview_adsb.py`.
Modify `main.py` at imports, persistent path constants,
`startup_event`, `shutdown_event`, and router registration.

**Interfaces:** Define the main plan's Pydantic wire models and immutable
settings values. `AdsbSettingsStore(path: Path)` exposes
`get() -> AdsbSettings` and
`update(changes: dict[str, object]) -> AdsbSettings`.
`set_overview_adsb_runtime(store: AdsbSettingsStore | None,
service: AdsbTrafficService | None) -> None` registers application dependencies;
use postponed annotations and a TYPE_CHECKING import for Task 3's service.
Settings operations
work with a store alone. `initialize_overview_adsb_runtime() -> None` initially
registers the store; Task 3 extends it to acquisition.

- [x] **Step 1: Write failing store and API tests.**
  `test_default_settings_are_off_with_revision_zero` asserts all six fields from
  the main contract. `test_partial_updates_preserve_lists_and_increment_revision`
  saves includes `[' 00ab12 ', '00AB12']`, then only mode; expect
  `['00AB12']`, preserved mode-independent lists/filter, and revisions 1 then 2.
  `test_callsigns_trim_deduplicate_ignore_blanks` saves
  `[' rch ', '', 'RCH', ' reach ']`; expect `['RCH', 'REACH']`.
  `test_conflicting_lists_are_preserved` asserts the same hex stays in both.
  `test_reopened_store_keeps_revision_and_settings` uses a second store instance.
  `test_two_store_instances_merge_under_lock` proves disjoint saves survive.
  Parameterize invalid hexes (`'12345'`, `'1234567'`, `'~AB1234'`, `'ZZ1234'`),
  nonstring entries, scalar lists, nulls, numeric/string booleans, unknown mode,
  unknown keys, supplied revision, and empty update: API 422, disk unchanged.
  Corrupt JSON and failed `os.replace` return 503 and preserve bytes, settings,
  and revision; temporary files are removed. Uninitialized store returns 503.
  Main-runtime tests assert registration, lifespan persistence and shutdown
  unregistration, following `test_main_overview_link_settings.py`; extend them
  in Task 3 for service/client cleanup alongside the existing orbital runtime.
  Pin the normalization/merge contract with these store assertions:

  ```python
  saved = store.update({"include_hexes": [" 00ab12 ", "00AB12"]})
  assert saved.include_hexes == ["00AB12"]
  assert saved.revision == 1
  changed = store.update({"mode": "included_only"})
  assert changed.include_hexes == ["00AB12"]
  assert changed.revision == 2
  ```

- [x] **Step 2: Verify failure.** Run the two new test files with `-q`;
  expect missing-model/store/router imports or missing endpoints.
- [x] **Step 3: Implement models and atomic settings operations.** Match Task 1
  signatures and the main contract. Validate before writing; create list defaults
  with factories. Reject corrupt existing state rather than overwriting it with
  defaults. The locked revision and settings share one atomic JSON record.
  Use existing `overview_link_settings.py` and its API as patterns. Mount settings
  GET/PUT, return complete confirmed state, and notify an installed service after
  successful persistence using Task 3's `settings_changed()`.
- [x] **Step 4: Register the settings runtime and verify.** Use
  `data/settings/overview-adsb.json`; unregister on shutdown. Run the new tests
  plus existing unit/integration `test_overview_link_settings*.py`; expect PASS.
  Also run `tests/unit/test_main_overview_adsb.py` and
  `tests/unit/test_main_overview_link_settings.py` for lifecycle registration.
  Inspect the existing Compose data mount; no new volume should be needed.
- [x] **Step 5: Commit only Task 1 files.**
  `git commit -m "feat(adsb): persist revisioned shared aircraft settings"`.

## Task 2: Provider normalization, filter precedence and freshness

**Files:** Create `app/services/adsb_lol.py`,
`app/services/overview_adsb_selection.py`, `tests/unit/test_adsb_lol.py`,
`tests/unit/test_overview_adsb_selection.py`, and
`tests/fixtures/adsb_lol/{military,explicit,malformed}.json`.

**Interfaces:** `AdsbLolProvider(client: httpx.AsyncClient,
time_source: Callable[[], float] = time.time)` exposes
`fetch_military() -> AdsbProviderResult` and
`fetch_hex(hex_code: str) -> AdsbProviderResult` (both async).
Define `AdsbProviderResult(contacts: list[AdsbContact], acquired_at_ms: float)`
in `adsb_lol.py`. Define `AdsbProviderError` with
`retry_after_seconds: float | None` for Task 3.
`normalize_contact(record: dict[str, object], response_now_ms: float,
acquired_at_ms: float, from_military_feed: bool) -> AdsbContact | None` is pure.
`position_state(contact: AdsbContact, now_ms: float) ->
Literal['current', 'stale', 'expired']` and
`select_contacts(contacts: Iterable[AdsbContact], settings: AdsbSettings,
now_ms: float) -> list[AdsbContact]` are pure selection exports.

- [ ] **Step 1: Write failing adapter/selection tests.** For response `now =
  1791028800000`, `seen_pos = 2.5`, assert position time `1791028797500`.
  Use the same envelope twice at later acquisition times and assert unchanged
  observation time. `lastPosition` with `seen_pos = 40` uses its own age when
  top-level position is absent/invalid. Never use `seen`, `rr_lat`/`rr_lon`,
  `gpsOkLat`/`gpsOkLon`, or message time to invent a position.
  Parameterize invalid ages: missing, negative, NaN, infinity, bool, string;
  future observation, absent timestamp, and nonfinite/out-of-range coordinates
  all return None. Test ±90 latitude and ±180 longitude as valid boundaries.
  Non-ICAO identities are rejected, including a leading `~`.
  `test_malformed_envelope_fails_but_invalid_record_is_isolated` distinguishes
  a missing/non-list `ac` or invalid `now` from one invalid aircraft among valid
  siblings. HTTP/JSON errors and non-success provider `msg` raise the provider
  error. Transport fixtures use `httpx.MockTransport`, not network requests.
  `test_optional_fields_and_classification` asserts flags 1/0/absent yield
  true/false/unknown on hex responses; `/v2/mil` supplies true provenance.
  Missing track stays null; trim callsign/registration/type; speed 0 is valid.
  Prefer finite numeric barometric altitude, then geometric, with `ft`/source;
  barometric 0 stays 0, `"ground"` is unavailable unless geometric is valid.
  Test Retry-After seconds and HTTP-date parsing with an injected fixed clock.
  `test_filter_precedence` covers overlapping lists, civilian inclusion,
  civilian `RCH123` rejection, included missing callsign, and disabled mode.
  `test_callsign_or_substrings` uses `['RCH', 'REACH']` against padded lowercase
  `xRCH123`, `REACH9`, nonmatches and missing callsign; empty filters admit all
  military background. `test_included_only_empty_is_valid` expects `[]`.
  `test_duplicate_newest_position_wins` supplies both endpoint records in both
  orders; one hex survives with the newest valid observation and its details.
  Test exact ages 29.999, 30, 30.001, 119.999, 120, 120.001 seconds; inclusion
  never bypasses expiry. Tie-break equal observation times by acquisition time.
  Given a fixture contact whose observation time is `1791028800000`, pin:

  ```python
  assert position_state(contact, 1791028829999) == "current"
  assert position_state(contact, 1791028830000) == "stale"
  assert position_state(contact, 1791028919999) == "stale"
  assert position_state(contact, 1791028920000) == "expired"
  ```

- [ ] **Step 2: Verify failure.** Run both new unit files with `-q`;
  expect missing adapter/selection exports.
- [ ] **Step 3: Implement the adapter and selectors.** Use the verified schema
  linked from the main plan; only `/v2/mil` and `/v2/hex/{hex_code}` requests.
  Convert `now - seen_pos * 1000` once; validate against acquisition time and
  reject future observations. Omit bad records; fail bad envelopes. Validate
  optional numeric fields independently; track must be finite in `[0, 360)`.
  Construct explicit units rather than passing untyped provider fields onward.
  Apply exclusions, inclusion, mode, military classification, then callsign OR;
  include position validity/expiry and normalized-hex deduplication throughout.
- [ ] **Step 4: Verify success.** Run Task 2 files and Task 1 unit tests;
  require PASS, including every boundary and malformed-data parameter.
- [ ] **Step 5: Commit only Task 2 files.**
  `git commit -m "feat(adsb): normalize provider positions and global selection"`.

## Task 3: Shared acquisition service, cache and traffic API

**Files:** Create `app/services/overview_adsb_traffic.py`,
`tests/unit/test_overview_adsb_traffic.py`, and
`tests/integration/test_overview_adsb_traffic_api.py`.
Modify `app/api/overview_adsb.py` runtime/traffic endpoint and `main.py`
ADS-B initialization, startup and shutdown; extend
`tests/unit/test_main_overview_adsb.py` for owned service/client lifecycle.

**Interfaces:** `AdsbTrafficService(store: AdsbSettingsStore,
provider: AdsbLolProvider, time_source: Callable[[], float],
monotonic_source: Callable[[], float])` receives clocks in seconds.
Exports `async start() -> None`, `async aclose() -> None`,
`settings_changed() -> None`, `async refresh_once() -> None`, and
`read() -> AdsbTrafficBundle`. `refresh_once` is the same serialized cycle used
by the scheduler and deterministic tests; `read` never calls the provider.
`settings_changed` synchronously reapplies confirmed settings and wakes the
scheduler. Task 1's initializer creates this service plus one httpx client;
startup awaits `start`, shutdown awaits `aclose` before closing the client.

- [ ] **Step 1: Write failing deterministic service/API tests.** Fake provider
  calls use controllable asyncio events; clocks are injected, no real sleeps.
  `test_viewers_share_one_cycle` issues concurrent refreshes/traffic reads and
  asserts one upstream cycle, identical revision/contact identity, max one cycle
  active, and zero upstream calls from reads. `test_disabled_never_acquires`
  asserts no calls before enable and no calls after confirmed disable.
  `test_mode_controls_acquisition` asserts military mode calls global military
  first; hex fallback only for included, nonexcluded aircraft without a current
  valid position in that result. Included-only calls only those hexes and never
  military; empty include list calls neither endpoint. Coordinates, viewport,
  mission, route and viewer count never appear in upstream inputs.
  `test_missing_position_does_not_renew_cached_contact` retains an original
  position through message-only/empty/malformed results, then removes at 120s.
  `test_older_duplicate_cannot_overwrite_cache` keeps newer position even if the
  older record was acquired later. `test_fresh_returning_inclusion_reappears`
  proves expiry leaves the saved include entry intact and later traffic returns.
  `test_source_failures_are_independent` fails military with a successful hex,
  then the reverse; contacts and per-source last success/errors stay independent.
  `test_backoff_and_retry_after` asserts failed source retry times 15, 30, 60,
  120, 240, 300 seconds, reset after success, and a longer Retry-After honored.
  Existing contacts still stale/expire while a source is backed off.
  `test_save_race_discards_obsolete_cycle` blocks requests, saves exclusion,
  included-only, or disable/re-enable, then releases old responses; assert latest
  revision and no restored excluded contact or old-generation classification.
  `test_shutdown_cancels_tasks_and_clears_ephemeral_cache` confirms cancellation,
  empty restarted cache with preserved settings/revision, and no leaked client.
  Traffic API tests cover disabled empty bundle, source errors in HTTP 200,
  settings unavailable 503, and GET filtering immediately after PUT exclusion.
  In the blocked-cycle fixture, after exclusion and release, assert:

  ```python
  bundle = service.read()
  assert bundle.settings_revision == store.get().revision
  assert "00AB12" not in {contact.hex for contact in bundle.contacts}
  ```

- [ ] **Step 2: Verify failure.** Run the new service/API tests with `-q`;
  expect missing service or missing traffic route.
- [ ] **Step 3: Implement acquisition scheduling and cache ownership.** Use one
  serialized task/lock, a generation per confirmed settings revision, and a
  wake event. Read settings at most one second apart to notice another store
  writer; PUT wakes immediately. Filter reads against current confirmed settings.
  Do not apply any result after its generation was superseded. Cancel disabled
  or obsolete source work and drop its cache when disabled; enable starts fresh.
  Normal cycles start no faster than 15s apart and never overlap; a long cycle
  schedules its successor after completion rather than catching up in a loop.
  Run hex lookups with concurrency at most 4 and httpx timeout 10s per request.
  Retry state is per `military`/hex key, not one global failure gate; exponential
  backoff is capped at 300s except longer provider Retry-After. Reset on success.
  Removed/excluded hex keys have no scheduled queries; drop irrelevant source
  status. Store only newest valid positions; retain previous ones to original
  expiry when no valid replacement arrives. Prune expired cache in reads/cycles.
- [ ] **Step 4: Implement traffic route and application cleanup.** Complete
  Task 3's interfaces. Use `https://api.adsb.lol` for the owned client and return
  generation-consistent revision/bundle snapshots. Sanitize source error text;
  never expose raw upstream bodies. If settings cannot be read, stop acquisition
  and return 503 until recovered. Neither ADS-B failure nor settings failure
  writes telemetry, warning rules, history, or mission services.
- [ ] **Step 5: Verify success.** Run all `test_overview_adsb*.py` unit/integration
  files and `test_adsb_lol.py`; require PASS. Also run existing history, clock,
  link-settings API tests and startup/health integration tests for lifecycle
  regressions. Inspect cancellation and source-call assertions, not just HTTP 200.
- [ ] **Step 6: Commit only Task 3 files.**
  `git commit -m "feat(adsb): share acquisition cache and revisioned traffic API"`.
