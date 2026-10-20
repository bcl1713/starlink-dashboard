# Operator archive review follow-up

This follows [the portability and resource review](https://github.com/bcl1713/starlink-dashboard/pull/381#issuecomment-6252029478)
of PR #381. It preserves one mission ZIP and the existing customer briefing,
export preparation and mission-plan import controls. Ordinary import leaves
both active Operator and telemetry databases untouched.

Production candidate: `5f3bc63695c596d4ebc71f5e2d6f0dbded17f026`.
[Production qualification and cleanup](production-summary.json),
[complete round trip](archive-roundtrip.json),
[size/resource probes](archive-limits.json),
[browser results](archive-browser.json),
[restart](archive-restart.json) and [failure](archive-failure.json).

| Check                                      | Observed result                                                      |
| ------------------------------------------ | -------------------------------------------------------------------- |
| Full-capture archive                       | 2 legs; 22 current records; 24 immutable revisions                   |
| Extracted customer PDF                     | Valid, independently readable, 2 pages                               |
| Large transfer ZIP                         | 154,703,848 bytes; imported through direct HTTP and production Nginx |
| Maximum ZIP                                | 2,147,483,648 bytes accepted                                         |
| Above application limit                    | 2,147,483,649 bytes rejected with application 413                    |
| Above Nginx envelope limit                 | 2,149,580,800 bytes rejected with Nginx 413                          |
| Uvicorn peak before/after uploads          | 291,774,464 / 294,436,864 bytes                                      |
| Storage/assembly stress process peak RSS   | 967,196,672 bytes                                                    |
| SQLite allocated file after release        | 155,525,120 bytes; zero live snapshots; pages reused                 |
| Quota rejection / expiry / scratch cleanup | Atomic rejection; snapshot and artifact removed                      |
| Desktop/mobile                             | 1920×1080, 390×844, 844×390; no browser errors                       |
| Runtime cleanup                            | No owned containers, networks, volumes, images or listeners remain   |

[Extractable mission ZIP](synthetic-complete-mission.zip) and
[customer briefing PDF](synthetic-customer-brief.pdf) contain synthetic data only.
The 148 MiB size fixture and 2 GiB boundary scratch files are removed by the
runner; its code and measured results are retained for reproduction.

## Compatibility changes

The application accepts a complete ZIP through 2 GiB using its existing
Starlette upload spool, without copying the ZIP into memory. Production Nginx
allows 2 GiB plus 1 MiB of multipart framing. Import separately bounds expanded
planning members at 100 MiB and bounds ZIP metadata before loading entries.
Archival members and the briefing PDF are not decompressed during plan import.

Export has explicit input, supplementary-file, per-snapshot and aggregate
snapshot capacities. Snapshot JSON is escaped in small chunks; fingerprints are
hashed incrementally. Quota reservation and job insertion are atomic. Recovery
reclaims terminal snapshots and snapshots for missing ready ZIPs; normal expiry
removes the snapshot and prepared artifact. See [operating limits](../../../operations/mission-journal-archive.md#size-and-resource-limits).

## Evidence scope

The end-to-end scenario uses real journal capture, real two-leg flight/archive
services, production PDF rendering, preparation, ZIP assembly, a separate clean
dashboard, production Nginx and the existing desktop/mobile browser controls.
It checks the two-page independently extracted briefing, full journal revisions
and checksums, per-leg archives, legacy import, repeated export, corrections,
restart and export failure.

The separate large fixture starts at the frozen supplementary-file boundary.
It exercises production snapshot persistence and ZIP assembly with 1,684,800
synthetic numeric CSV observations representing 36 hours, 13 channels at 1 Hz.
It is a storage/assembly and transfer-capacity test, not evidence that this dense
history fits the 128 MiB source capture guard. Source-capacity regressions verify
explicit whole-export rejection, with no truncation or mutation of source data.

The assembled ZIP compresses to about 11 MiB. Repacking the identical members
with ZIP STORE produces about 148 MiB; both the direct import HTTP endpoint on
the separate instance and the production Nginx endpoint import it successfully.
Compression method is not an import contract. The archive retains its journal,
telemetry and briefing members during these tests.

Separate sparse-preamble ZIP boundary probes send actual request bodies at
2,147,483,648 bytes (accepted), one byte above (application 413), and 2 MiB above
(Nginx 413). These probes validate the real deployed limits; they are not
telemetry-size estimates. They use bounded disk spools and are removed after
qualification.

The large live snapshot also exercises quota rejection and database page reuse.
The database retains its allocated file size after row deletion, while its live
snapshot count returns to zero. Actual Uvicorn high-water RSS and stress-process
peak RSS are recorded separately. Export memory scales with capture size and
Python object expansion; it is not a constant-memory capture implementation.

No merge is authorized by this evidence. The PR remains open for review.

## Regression verification

The frontend suite passes all 1,844 tests and the production build passes.
The final preparation/recovery suite passes 19 tests; the combined focused
archive/import/fixture suite passes 25 tests, and standalone harness checks pass
16 tests. Logs are included alongside this report. Final full backend/static
results are available through [the PR checks](https://github.com/bcl1713/starlink-dashboard/pull/381/checks).

The first full backend run exposed two import lifecycle tests receiving `429`
because the new upload boundary tests consumed their shared rate-limit storage.
The boundary test class now resets its test-only limiter storage before and
after each case. Production import remains limited to five requests per minute.
The combined lifecycle/import group passes all 47 tests after this isolation
fix. The full backend suite is rerun as well.
