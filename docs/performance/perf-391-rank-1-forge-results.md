# Rank 1 Task 3: Forge preflight, 2026-10-22

**STOP: the Forge dependency preflight failed. No performance measurements were
started, and Task 3 remains incomplete.** This is a dependency comparability
failure, not an application failure. The unchanged requirements installed
FastAPI 0.159.1; the original component benchmark recorded 0.158.1.

The approved [measurement protocol](perf-391-rank-1-measurement.md) requires
identical package inventories, says “do not substitute software versions”, and
requires stopping on a workload/package mismatch. No version substitution,
application edit, threshold change, soak or retry was attempted. Restoring an
approved dependency inventory requires review before another Task 3 attempt.

## Source and environment identities

The isolated worktree is `.worktrees/perf391-rank1-task3-forge`, on
`perf/391-rank1-task3-forge`, created from `origin/dev` and fast-forwarded to
the preserved head of pull request 406. The primary checkout remains on `dev`.

| Input                             | Observed identity                                              |
| --------------------------------- | -------------------------------------------------------------- |
| Host                              | `forge`; Intel i9-10900K; 20 logical CPUs                      |
| Kernel                            | `7.0.0-34-generic`, x86_64                                     |
| Configured user Docker            | `unix:///run/user/1002/docker.sock`; default context preserved |
| Docker server                     | 29.8.1; overlayfs; 20 CPUs; 65,915,523,072 bytes memory        |
| Node                              | v22.12.0, existing `/home/oracle-worker/.local/bin/node`       |
| Existing browser package          | `@playwright/test` 1.63.0                                      |
| Chromium and headless shell       | Revision 1243; 153.0.8010.12; both version commands succeeded  |
| Private component Python          | 3.11.16, matching the original component interpreter           |
| Historical production Python      | 3.11.17; no new production image built                         |
| Current dev baseline              | `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96`                     |
| Original application              | `25e34168f0e2cecb149b0323f1f5a795cb28cae0`                     |
| Uncorrected application / PR #403 | `e1f657986f7b988a967ddd2bef8ca4626e30b5de`                     |
| Corrected application, Task 2     | `3cd79e2a`                                                     |
| PR #405 / approved plan           | `f7253c687041342ee080b0197f0b98f20eaefdfe`                     |
| pull request 406 at preflight     | `4ec1e7f13b56623c8f83f1ae05f768d736325b32`                     |
| Frozen strict harness             | `13cbf1d5`                                                     |
| Frozen availability-v2 harness    | `f3029024b5950a267645195476da5cbca326f16a`                     |

The recorded Forge hardware, Docker, Node and Chromium identities match the
retained original evidence. Both frozen harnesses were clean and unchanged. The
existing primary browser dependency root remains `frontend/mission-planner`; no
browser or package installation was performed there. Chromium version checks do
not establish a successful rendered workload. Production image package equality
and full browser workload readiness remain unverified because of the dependency
stop.

The original component evidence at
`perf391-independent/.superpowers/perf391-independent/component-final/component.json`
records these packages; the private environment was installed from the unchanged
candidate `requirements-dev.txt` with Python 3.11.16:

| Component package | Original | Forge preflight | Identity       |
| ----------------- | -------- | --------------- | -------------- |
| Pydantic          | 2.14.1   | 2.14.1          | Match          |
| prometheus-client | 0.26.0   | 0.26.0          | Match          |
| filelock          | 4.2.4    | 4.2.4           | Match          |
| FastAPI           | 0.158.1  | 0.159.1         | Mismatch: stop |

The complete newly resolved Python inventory and installation log are retained;
these four rows are the original component probe's recorded package subset, not
a claim of complete inventory equality.

## Evidence and measurement accounting

The original raw Task 6 evidence root is accessible on Forge. All 5,385 files in
`perf391-task6-manifest.json` and all 317 files in the earlier
`perf391-task6-availability-v2-manifest.json` were rehashed with zero missing or
mismatched files. The manifests overlap; their counts are not unique-file
counts. The original diagnostic and component evidence directories are also
accessible.

The [cloud preflight report](perf-391-rank-1-results.md) and its manifest from
`4ec1e7f1` remain byte-for-byte unchanged. That report documents a separate,
noncomparable cloud attempt and is not an application failure or Forge result.

Component, four-role production off/counters, and unloaded/loaded off/trace
cohorts each have zero started runs and zero accepted pairs in this attempt.
There are zero rejected measurement runs; the failed prerequisite is recorded
separately. Backend CPU savings, producer CPU, admission contention, latency and
run-to-run variability are therefore **unavailable**, with no performance claim.
Public preparation/source-binding spans bypassed by the private main path remain
unavailable, never zero-cost. The 1.5-second gate and historical NO-GO remain.
Canonical backend/static tests and new exact-head CI qualification were not run
after the preflight stop; no previous CI result is presented as a new pass.

The [Forge manifest](probes/perf391-rank1-task3-forge-manifest.json) records the
private evidence path, hashes, command outputs, inventories and cleanup checks.
The initial sandbox fetch failed because `.git/FETCH_HEAD` was read-only; the
initial GitHub request could not connect and the sandbox Docker request was
permission-denied. Approved host commands subsequently succeeded using the
configured user daemon. These sandbox access failures are not Forge failures.

## Cleanup and review status

Host-level `ps`, listener inspection and configured-daemon container/network/
volume listings were retained. No task server, browser context, worker, image,
Compose project, container, network, volume or listener was started. Chromium
version processes exited. The private Python environment was removed after
inventory capture. The Docker listing showed no containers, only default
networks and three existing `configuration-preview-*` volumes; those shared
volumes were preserved. Shared credentials, caches and runtime configuration
were preserved. Evidence and the isolated worktree remain for review.

At preflight, #403, #405 and #406 were all draft, open and based on `dev`. No
merge, deployment, 60-minute soak or closure of #391 was performed. Task 3
remains blocked pending review of the dependency mismatch.
