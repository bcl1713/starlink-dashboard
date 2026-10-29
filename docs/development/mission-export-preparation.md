# Mission export preparation

Mission ZIP exports use explicit preparation. POST
`/api/v2/missions/{mission_id}/export-preparations` returns a job reference; GET
the returned job path for queued/preparing/ready state and DELETE it to cancel
that export's work. Download only through the ready job's `download_url`.
Preparation has a 600-second aggregate deadline; ready files expire after 30
minutes. Each request freezes committed planning inputs before telemetry
generation; later mission saves and live updates do not cancel that snapshot. A
completed download keeps its labeled snapshot and does not switch to later
edits.

Legacy POST `/api/v2/missions/{mission_id}/export` returns 200 for a current
already-ready ZIP, otherwise 202 JSON with a `Location` status URL. Clients must
poll that preparation and then fetch its download, rather than saving the 202
JSON as a ZIP. A cold download never waits for PDF rendering. Cancellation and
download disconnects do not stop shared customer slide preparation.

A retry after an omitted customer PDF creates a new preparation for the same
inputs. Its original ready ZIP remains an immutable download until expiry.
Terminal-job cleanup releases local captures, including requests assembled by
another elected worker.

Requests copy matching prepared customer pages with the planning inputs. An
optional PDF that is still preparing is omitted with the existing warning; data
delivery does not wait for new rendering. The planning snapshot and copied pages
are persisted with the job so another worker or a restart does not replace them
with a later plan. Their bytes count toward the shared export storage quota.

## Observed telemetry artifact

Pass `artifact_kind=telemetry` when starting export preparation to request the
observed flight archive instead of the planning package. The normal default
remains planning. Incomplete or unrecorded legs require explicit
`allow_partial=true`; the ZIP manifest and preparation warning mark the result
partial. Use the same polling, cancellation, ready-download and expiry flow.

Telemetry preparation pins capture revisions at request time. Corrections create
new revisions; a ready download keeps its original bytes. Temporary download
files expire after 30 minutes while the durable source archives remain intact.
Operational packages contain live sources only. Each leg contains versioned
`observations.csv`, `events.csv`, and `manifest.json` files, in mission leg
order. The outer manifest records completeness and file checksums. Missing
values and unknown source freshness remain explicit, separate from measured
zero.

Raw extraction has its own persisted interval jobs; regular live samples do not
prove that all Prometheus label series were captured. Empty, partial and failed
queries retry with capped backoff. After twelve unsuccessful attempts for an
interval, finalization preserves all available data in an explicitly incomplete
sealed revision and releases its rolling-data retention pin. The manifest names
unresolved raw intervals and missing metrics. A later explicit event correction
creates a new revision and retries missing source history, reusing observations
from prior sealed revisions even after the rolling buffer has expired.

## Complete mission archive and plan transfer

Mission export supports `telemetry_format=full` (the default) and
`telemetry_format=compact` on both preparation entrypoints. The mission export
dialog offers the same Full detail / Compact lossless selection. Both preserve
individual observations, UTC/source timestamps, missing values, source labels,
GEP/IP metadata and the complete archived Operator journal. Neither averages nor
downsamples telemetry.

Compact telemetry replaces repeated metric names and label JSON in observation
rows with a `series_id`. Join each leg's `observations.csv` to that leg's
`series.csv` on `series_id`; the dictionary supplies the complete `metric` and
`labels_json`. Each telemetry archive includes `dataset.json`, a README and
checksummed per-leg manifests. Analysis and after-action reports remain separate
from export. The historical Prometheus CSV at `/export` remains available with
its existing selectable query resolution.

Active observations stream from a pinned WAL read transaction. Sealed capture
TEXT streams directly from SQLite through bounded readers. Telemetry is frozen
in an owned, immutable disk sidecar rather than materialized as large Python
collections or CSV strings embedded in JSON. Recording writers can commit while
export reads retain their snapshot. Restarted jobs retain the same captured
bytes; inline snapshots from older versions remain readable.

The 256 MiB uncompressed supplementary-member cap remains finite and includes
journal, telemetry, dictionaries and dataset descriptions. Storage reservations
cover temporary sidecars, indexes, planning spools and final ZIPs concurrently;
ready downloads still expire after 30 minutes. Capacity failures return a
specific `mission_archive_capacity` error and preserve source archives. A
disconnect, cancellation or capture deadline also releases unacknowledged work.

The isolated large-archive production probe uses synthetic observations only:

```sh
STARLINK_ACCEPTANCE_PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  timeout --kill-after=10s 90m python tools/acceptance/mission-archive/run.py \
  --candidate "$(git rev-parse HEAD)" \
  --project starlink-operator-large-export-example \
  --evidence /tmp/starlink-large-export-example
```

It reconstructs observations from full and compact ZIPs above the old input
budget, tests sealed data after rolling deletion and high-cardinality labels,
measures recording-writer latency during a paused read, and exercises both
preparation entrypoints plus rendered selection/error/abort behavior through
production Nginx. Its owned runner removes runtime resources after completion.

The normal mission ZIP also captures the enabled Operator journal and the
per-leg telemetry archives from issue #349. It preserves customer PDF generation
and the same planning/import files and controls. Journal files are checksummed
under `operations/`; existing telemetry members retain their schemas under
`telemetry/`. Capture boundaries are sequential and explicitly labeled. Zero-leg
drafts remain exportable with telemetry marked not applicable.

Ordinary import transfers planning data only; it never restores the archived
Operator journal or telemetry into active destination stores. Keep the original
ZIP as the historical record. See
[Mission ZIP journal archive](../operations/mission-journal-archive.md) for
contents, independent validation, retention, restart and rollback behavior.
