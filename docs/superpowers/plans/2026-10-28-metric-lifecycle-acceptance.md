# Metric lifecycle acceptance follow-up

> **For agentic workers:** Use the existing isolated Issue 393 worktree and
> execute the independent contract and evidence tasks in parallel, then run
> the exact committed candidate. Keep PR #432 draft pending all gates.

**Goal:** Address review 5682783162 without rewriting the metric lifecycle fix.

**Architecture:** Keep product behavior intact. Update the V2 acceptance journey
and its observation validator together to require route-bound map POIs and the
current one-second polling lifecycle. Preserve production Dockerfiles, Nginx,
platform-owned browser authority, provenance and cleanup checks.

**Tech stack:** Python acceptance platform, Node/CDP journey, Docker Compose,
Prometheus, existing provisioned Chromium.

**Spec:** [PR review](https://github.com/bcl1713/starlink-dashboard/pull/432#pullrequestreview-5682783162).

## Constraints and review focus

- Keep customer Overview POIs on the map; do not add forecast tables.
- Require distinct visible KAAA/KBBB markers bound to the uploaded active route.
- Preserve real navigation, request completion, cadence and overlap checks.
- Reject incomplete, duplicate, hidden or stale browser observations in tests.
- Preserve the earlier 3,599.999954706-second result and false duration flag.
- Associate every run with its actual candidate/base, not a moving dev label.
- Track and clean only owned processes, ports, containers and private volumes.

## Tasks

- [x] Merge dev at `44d09d59f6eb60142e6f9ac0a0b676a6a019e353`.
- [x] Update contract, journey, validator, negative tests and operational docs;
      run the focused tooling tests with an explicit wall-clock timeout.
- [x] Publish the previous diagnostic raw samples, provenance and cleanup
      receipts with checksums and a clear headless diagnostic limitation.
- [ ] Run canonical static checks, review the combined diff, commit and push.
- [ ] Run fresh platform health/static/final on that exact candidate using the
      provisioned browser and production Dockerfiles; retain sealed evidence.
- [ ] Run the production diagnostic soak with 120-second warmup and
      3,620-second measurement; require measured span >= 3,600 seconds without
      changing the prior result or manually overriding the flag.
- [ ] Verify independent host/Docker cleanup, make the new evidence reviewable,
      refresh integrated CI and PR wording with exact SHA/base identities.
