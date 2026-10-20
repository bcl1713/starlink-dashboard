# Task 4: Durable rolling buffer and resumable capture

**Files:** Create app/services/telemetry_archive/reader.py, store.py,
coordinator.py, tests/unit/test_telemetry_archive.py and
tests/integration/test_telemetry_archive_recovery.py. Modify backend
lifecycle/ingestion owners identified in Task 1, app/core/config.py,
docker-compose.yml and docs/setup/configuration/storage-configuration.md.

**Interfaces:** ArchiveReader.read(start: datetime, end: datetime, mode: str) ->
ArchiveBatch; ArchiveStore.append(batch: ArchiveBatch) -> Checkpoint;
CaptureCoordinator.apply_event(event: FlightEvent) -> CaptureState;
CaptureCoordinator.recover(now: datetime) -> list[CaptureState]. ArchiveBatch
preserves source metric name, allowlisted labels, scrape time, available source
observation time, value and availability. CaptureState includes leg identity,
bounds, revision, gaps, watermark and pending work.

- [ ] Add failing tests asserting start = off_blocks_at − 1800 seconds and end =
      first destination on_blocks_at + 1800 seconds. A later ground move does
      not change either bound. Overlapping planned-leg buffers preserve both
      windows with explicit shared coverage metadata.
- [ ] Add tests for short startup history, missing/stale/zero distinctions,
      public-IP changes, multiple label series, and simulation segregation.
      Assert secrets and non-allowlisted labels never reach files.
- [ ] Add restart/outage/failure-injection cases: crash after chunk publication
      but before watermark commit, unavailable Prometheus, disk full, retention
      expiry, corrected boundaries, and two competing workers. Assert idempotent
      samples, visible gaps, recoverable pending jobs, and exactly one published
      revision.
- [ ] Run failing tests. Implement a durable rolling pre-event buffer with at
      least 35 minutes retention and incremental extraction with bounded chunks,
      source sample identity and overlapping retry windows. Use raw range-vector
      samples where required to avoid fabricating scrape timestamps through
      query_range lookback. Record scrape time separately from application
      observation time.
- [ ] Use SQLite transactions for work ownership and watermarks, atomic chunk
      publication, and explicit recovery of orphaned writes. Pin chunks when an
      off-blocks candidate begins, including its preceding 30 minutes; keep them
      pinned until candidate rejection or capture ownership is durable. The
      extra five minutes is a recovery margin, not a replacement for pinning.
      Retain prebuffer chunks referenced by active captures or undelivered
      outbox events. On startup, recover candidate pins and consume pending
      events before buffer garbage collection. If downtime exceeds available
      history, report the exact gap. Delete only unreferenced expired buffer
      chunks; never auto-delete sealed mission archives under the buffer
      retention policy.
- [ ] Add tests with delayed off-blocks confirmation while Prometheus history is
      unavailable, asserting the complete 30-minute pre-event interval remains
      pinned. Inject crashes after event commit before delivery, after capture
      work commit before acknowledgement, and during correction delivery; assert
      replay creates exactly one capture revision and preserves its history.
- [ ] Complete the manual-only capture acceptance deferred from Task 3: create
      absent historical events, recover available history, and assert explicit
      gaps and correct capture revisions. Integrate archive impact previews into
      the manual correction UI now that capture state exists; display the
      affected revision and unrecoverable history without pretending absent
      source data can be recovered.
- [ ] Persist on a backend-owned mounted volume. Keep archive data independent
      of the existing 30-minute download-job expiration. Collection failure
      exposes archive health without changing operational controls. Retry
      recoverable failures with capped backoff and retain unresolved gaps rather
      than silently mark complete.
- [ ] Run focused recovery tests and backend tier; document volume ownership,
      backup and archive growth. Commit the independently testable capture
      service.
