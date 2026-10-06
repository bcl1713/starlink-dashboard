# Aviation weather Phase 1 implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the
> independent normalizer and frontend tasks; the controller implements their
> shared runtime interfaces. Do not run competing full suites.

**Goal:** Deliver production METAR/SPECI, TAF and international SIGMET with
Configuration preferences and native Overview rendering.

**Architecture:** Shared bounded backend leases fetch fixed AWC sources and run
bulletin normalization in a disposable constrained worker. Immutable local
GeoJSON is wrapped by the provider-neutral catalog. Browser validators admit
payloads before station/advisory rendering; radar keeps its existing owner.

**Tech Stack:** Python 3.11, Pydantic/FastAPI/httpx, Shapely, TypeScript/Zod,
React Query, Three, Vitest/pytest and the provisioned Playwright browser.

**Spec:** [Phase 1](../specs/2026-10-06-aviation-weather-phase-one.md) and
[catalog boundary](../specs/2026-10-06-aviation-weather-catalog.md).

## Global constraints

- Default-off and independent METAR, TAF, SIGMET preferences.
- METAR/SIGMET poll five minutes; TAF ten minutes.
- Two HTTP exchanges, 20 attempts/minute, 30-second absolute exchange timeout.
- Input gzip 8 MiB; expanded XML 32 MiB; worker one CPU/1 GiB, 120 seconds
  followed by 10-second termination grace.
- Station/advisory caps 5,000/500; 100,000 polygon vertices.
- Published station subsets at most 1 MiB/layer with disclosed omissions;
  oversized advisories fail admission and retain still-valid previous data.
- Browser encoded/decoded/GPU limits 16/32/16 MiB including replacements.
- METAR stale 75 minutes, expires 120 minutes from observation; forecasts retain
  half-open per-feature validity. Missed feed polls produce stale status.
- No new Overview weather controls or provider-specific frontend parsing.
- Exact candidate acceptance, bounded commands and verified task teardown.

## Review focus

1. Real AWC caches include missing-coordinate sentinels and imperfect forecast
   groups; safe records must remain usable with explicit incomplete coverage.
2. Unknown ceiling, variable wind and visibility bounds must not fabricate VFR.
3. Last-reader cancellation, disable and shutdown must reap normalization
   workers.
4. Expired/cancelled polygons and unknown altitude must not claim active
   coverage.
5. Replacement admission includes retained data; source failures preserve the
   original finite expiry, not a new age.

### Task 1: Catalog and shared runtime

**Files:** Backend `app/models/aviation_weather.py`,
`app/api/aviation_weather.py`,
`app/services/aviation_weather/{runtime,settings,transport,decode,worker,catalog}.py`,
`main.py`; frontend `src/services/aviation-weather.ts`.

**Interfaces:** `AviationWeatherService.products()`, `admitted_products(now)`,
`payload(instance, filename)`, `settings_changed(settings)`, `aclose()`;
`AviationSettingsStore.get/update`; normalized collection worker call
`normalize_in_worker(layer, body, now)`; `aviationWeatherApi` and strict
parsers.

- [x] Verify baseline radar tests before code changes.
- [x] Write envelope/API/lease tests and observe missing-feature failures.
- [x] Implement strict envelope parity and existing radar manifest
      compatibility.
- [x] Implement atomically saved settings, shared leases, immutable snapshots,
      finite stale retention, fixed-source HTTP bounds and disposable workers.
- [x] Review source-failure, settings race, worker and replacement budget tests.

### Task 2: Source normalizers

**Files:** Backend `app/services/aviation_weather/normalization.py` and
`tests/unit/test_aviation_weather_normalization.py`.

**Interfaces:** `normalize_metar(raw_xml, now_ms)`,
`normalize_taf(raw_xml, now_ms)`, `normalize_sigmet(raw_geojson, now_ms)` return
normalized GeoJSON with source identity, real retrieval time, incomplete feed
semantics and omissions.

- [x] RED/GREEN tests for SI values, nulls, ceilings, groups and validity.
- [x] Preserve station/issuer/report identity, cancellation, vertical
      references, unlocated textual advisories and antimeridian holes.
- [x] Verify bounded real-source METAR, TAF and SIGMET captures.
- [x] Complete independent normalization review.

### Task 3: Browser delivery and native layers

**Files:** Frontend `src/services/aviation-features.ts`,
`src/pages/aviation-weather/`, hooks, Configuration/Overview integration.

**Interfaces:** Strict GeoJSON features and catalog/settings APIs from Tasks
1/2.

- [x] Write failing feature, settings, lifecycle and native geometry tests.
- [x] Implement confirmed Configuration preferences and settings propagation.
- [x] Implement visibility/network-aware bounded payload ownership with hash and
      byte validation, fencing and expiry independent of simulation time.
- [x] Render station/forecast symbols and tessellated advisory polygons locally.
- [x] Add passive source/type/age/validity/legend/attribution/coverage status.
- [x] Run focused tests/build and independent frontend review.

### Task 4: Production acceptance and delivery

**Files:** Exact-SHA acceptance fixtures/journey, API/feature docs and report.

- [x] Run backend/frontend suites and lint; resolve integration regressions.
- [ ] Run isolated production Docker/Nginx/native browser acceptance at desktop,
      fullscreen and mobile; retain core/radar regression and cleanup evidence.
- [ ] Complete whole-branch review, fix findings, and preserve final evidence.
- [ ] Push feature branch and submit PR against dev; keep issue 290 open.
