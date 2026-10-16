# Task 6: End-to-end acceptance and execution handoff

**Files:** Create backend tests/integration/test_mission_telemetry_archive.py
and frontend tests/e2e/overview-flight-events.spec.ts; update
docs/development/mission-export-preparation.md and the flight-events report.

**Interfaces:** The public contracts from Tasks 1–5; no new runtime interface.

- [ ] Add a failing full-flow fixture for two legs including taxi out, flight,
      landing offset from the terminal coordinate, a DV offload park, later
      repositioning and a subsequent leg. Include an intermediate fuel stop
      within one leg. Assert first-park semantics, both buffers, mission
      ownership, UI state and ordered package contents.
- [ ] Execute the fixture through live-mode adapters with controlled synthetic
      source observations. Separately test simulation exclusion. Include backend
      restart and a bounded Prometheus outage near arrival.
- [ ] Verify archived CSVs after removing the test source's retained time range.
      Run focused suites, then repository canonical static, backend and frontend
      tiers with wall-clock limits and the required reviewed base revision.
- [ ] For UI changes, perform repository-required exact-revision browser
      acceptance at 1920×1080. Record evidence showing taxi out, landed/taxi in,
      parked, uncertain state and telemetry preparation. Do not present
      synthetic acceptance as real-flight calibration.
- [ ] Record actual results, unresolved field-calibration limits and storage
      configuration. Self-review spec coverage, signatures and archive
      ownership. Perform the selected execution method's independent code review
      before proposing integration.
- [ ] Stop and verify all task-owned runtime resources. Preserve review evidence
      and the open feature worktree. Submit changes against dev under repository
      workflow; merging or deploying is a separate action governed by user
      authorization.
