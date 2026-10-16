# Task 5: Versioned CSVs and mission telemetry packages

**Files:** Create app/services/telemetry_archive/package.py and
tests/unit/test_telemetry_package.py; modify
app/mission/package/preparation_routes.py, preparation_worker.py and their
tests. Create frontend src/services/telemetry-archives.ts; modify the existing
mission detail export UI after identifying its owning component.

**Interfaces:** prepare_telemetry_package(mission_id: str, revisions: tuple[str,
...], allow_partial: bool) -> PreparedTelemetryPackage. Extend preparation with
artifact_kind='telemetry' while preserving the current planning default. Package
inputs are pinned to sealed capture revisions. PreparedTelemetryPackage includes
completeness, ordered leg manifests and immutable package location.

- [ ] Add failing tests for ordered two-leg ZIP content, schema version, UTC
      event boundaries, missing-data intervals, source mode, checksums, stable
      ZIP metadata and deterministic bytes for identical revisions.
- [ ] Add test_correction_does_not_mutate_prepared_download: correction produces
      a new capture revision and package; the prior ready download retains
      original bytes until its ordinary expiration. Expiration may remove the
      temporary ZIP but must preserve source archives.
- [ ] Add partial/incomplete mission, pending extraction, simulated capture and
      cancellation tests. Default completed export rejects silently incomplete
      content; explicit partial export labels it in status and manifest.
- [ ] Run failing tests; implement schema version 1 with observations.csv,
      events.csv and manifest.json per leg. Preserve ordered segments and stops,
      metric/label identity, null values, available provenance, and correction
      history. Protect CSV text cells against spreadsheet formula execution
      without changing numeric values.
- [ ] Integrate with existing preparation polling/cancellation and download
      behavior. Add a distinct telemetry action and display
      pending/partial/ready state. Reuse preparation machinery without coupling
      source archive lifetime to job cleanup.
- [ ] Run package, existing export-preparation and frontend mission detail
      regression tests. Commit the third functional increment.
