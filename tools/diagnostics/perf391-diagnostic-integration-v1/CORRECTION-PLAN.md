# Diagnostic correction implementation plan

Spec: PR #408 comments 6368261902 and 6368326352; baseline
09095e263d3d1c237309b9f2359fa879b91353d2. Execution is inline.

Only diagnostic source and focused offline fixtures change. Historical evidence,
receipts, frozen tools, image IDs and production application code stay
immutable. No image/asset rebuild or A/C execution. The 1.5-second cadence gate
stays intact.

- [x] Extend the existing probe fixture with the retained authentic latency
      artifact, four 1,801-sample traces and full 36-character IDs. Exercise two
      commits through real probe, binding, collection and hash-addressed
      snapshots; compare every number and provenance ID. Observe failure, then
      replace conservative snapshot charging with exact encoded JSON accounting
      within the unchanged 2 MiB cap. Keep depth, node, string, point, queue and
      concurrency bounds. Reject oversized/deep input.
- [x] Extend fake-Page observer fixtures for reason-coded failures,
      stale/duplicate and interrupted assemblies, disposal faults and pre-close
      counters. Keep bounded reason history and explicit overflow accounting.
      Record screenshot stage and metadata with the existing deadline, without
      changing mandatory chart gates.
- [x] Factor only owner selection/finalization into an offline-testable helper.
      Retain actual passing readiness state, selected metadata, last
      frontend/observer state and Finish inputs/result. Test absent/invalid
      Finish, nonquiescence, incomplete commits and metadata timeout. Do not
      invent successful commits.
- [x] Extend the existing fake-Docker/real-Owner executor fixture to force
      browser failure. Preserve bounded stop/drain/export/statistics before
      volume removal; require present final counters, retain missing evidence as
      unavailable, retain original failure. Verify owned workers are reaped even
      on export faults.
- [x] Run focused tests with wall-clock limits, scoped format/syntax checks and
      independent artifact hash comparisons. Record exact source/evidence hashes
      in a new correction layer; do not rewrite predecessor manifests or
      compiled assets. Review diff, push to draft #408, verify cleanup and stop
      for checkpoint review.

Review focus: escaped/Unicode JSON charging, node/depth exhaustion, partial
assemblies cleared at close, optional screenshot vs mandatory chart loss,
missing backend statistics or stop/copy failure. Each belongs to the
corresponding fixture.
