# Mission export preparation

Mission ZIP exports use explicit preparation. POST
`/api/v2/missions/{mission_id}/export-preparations` returns a job reference; GET
the returned job path for queued/preparing/ready state and DELETE it to cancel
that export's work. Download only through the ready job's `download_url`.
Preparation has a 600-second aggregate deadline; ready files expire after 30
minutes. A saved change supersedes a pending export. A completed download keeps
its labeled snapshot and does not switch to later edits.

Legacy POST `/api/v2/missions/{mission_id}/export` returns 200 for a current
already-ready ZIP, otherwise 202 JSON with a `Location` status URL. Clients must
poll that preparation and then fetch its download, rather than saving the 202
JSON as a ZIP. A cold download never waits for PDF rendering. Cancellation and
download disconnects do not stop shared customer slide preparation.

A retry after an omitted customer PDF creates a new preparation for the same
inputs. Its original ready ZIP remains an immutable download until expiry.
Terminal-job cleanup releases local captures, including requests assembled by
another elected worker.

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
