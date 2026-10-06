# Aviation weather GFS foundation verification

This foundation implements the first half of the
[approved Phase 2 spec](../superpowers/specs/2026-10-06-aviation-weather-phase-two.md).
Native pressure-level U/V/T products use the isolated scientific worker and the
production API/Nginx path. Flight levels, model renderers and Configuration
controls belong to the subsequent presentation PR. Model settings remain off by
default.

## Evidence and scope

Each acceptance run has a SHA-qualified directory containing `candidate.json`,
image IDs/revision labels, source manifests, independent geographic samples,
browser screenshots/trace, cgroup measurements, failure controls, cleanup
inventory and shared-platform checksums. Final evidence is retained under
`/srv/starlink-acceptance/evidence/issue-290/final/starlink-290-gfs-foundation/`.
The PR's exact head must pass a no-cache production build and the complete
runner before integration; a report commit does not stand in for that head's
evidence.

The source fixture is NOAA GFS 2026-10-06 00Z F006 at 500 hPa with surface
pressure, using the strong validator `7a8c1bb19de384dc3052fae6aeee2efc` and
object size 539,601,570 bytes. The index SHA-256 starts `3e2b4b7b102978fe`; full
index and four GRIB hashes are pinned in the runner and retained in evidence.
U/V/T hashes match the sealed Phase 0 capture. No decoded grid, model envelope
or renderer output substitutes for production processing.

The native radar/METAR/TAF/SIGMET browser regression uses current source-shaped
fixtures. It is followed by a fresh private runtime with one shared historical
UTC anchor for model source replay. Separate volumes preserve production clock
rollback protection. SwiftShader software rendering and historical source replay
are explicit labels. These controls do not establish current live source
availability or minimum-host hardware performance for enabled deployment.

## Measured diagnostic baseline

Candidate `1073d699032736c3738d0d7fe6aeed36d80ba673` passed every runtime
control and cleanup check in a cached diagnostic build. It is not the required
no-cache final acceptance. Measurements below describe that candidate only; the
final head's separate evidence records its fresh image identities and
measurements.

| Measurement                                | Observed value           |
| ------------------------------------------ | ------------------------ |
| Scientific normalization wall / CPU        | 0.669 / 0.659 s          |
| Scientific child peak RSS                  | 159,644 KiB              |
| Worker and child aggregate peak memory     | 161,226,752 bytes        |
| Worker cgroup CPU across all controls      | 2,687,893 microseconds   |
| Artifact disk after controls               | 4,484,914 bytes          |
| Source fixture response bytes across tests | 8,868,562 bytes          |
| Encoded U/V/T and shared mask              | 1,819,440 bytes          |
| Maximum error at ten independent samples   | 0.0021875 physical units |

The worker cgroup enforced one CPU and 1 GiB memory across parent and child,
with no OOM events. Samples include both sides of the longitude seam, exact
poles, near-pole and ordinary coordinates. Conservative terrain/missing masks
remain distinct from valid zero wind. Buffer lengths and hashes were verified
through Nginx, including descriptor delivery and ETag 304 revalidation.

## Failure and regression controls

Acknowledged disable denied all prior immutable paths and stopped/reaped a
blocked scientific child within the 15-second API bound. Killing an owned child
and returning an incorrect source ETag both prevented publication. Thirty-two
concurrent core status requests remained successful below two seconds while the
scientific child was blocked. Source attempts respected the persistent budget
between scenarios. Every run stopped its private Compose project immediately;
host checks verified no owned processes or listeners, and project inventories
verified no containers, networks or disposable volumes.

Acceptance test cases reject dirty/wrong candidates, absent browsers, failed
decode or acknowledgement, missing/nonfinite measurements, live listeners,
surviving resources and teardown errors. A real socket test distinguishes closed
TIME_WAIT connections from live listeners. A shared replay-clock regression
prevents artificial per-process clock drift from weakening production guards.

The complete backend suite passed 2,106 tests with 20 pre-existing skips and two
dependency warnings before the added replay-clock test; that added test passed
separately. The full frontend suite passed 1,241 tests, plus lint and build.
Affected tooling passed 36 tests before the added listener test, which passed
with the other 24 acceptance/Compose checks. The complete static gate passed.
Required GitHub gates passed on the diagnostic head; the final head is gated
again before integration. Broad tooling collection additionally requires the
existing satellite/comparison proof dependencies, outside this foundation's test
environment.
