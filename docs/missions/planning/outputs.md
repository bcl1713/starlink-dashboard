# Mission exports

Use **Export** for a mission to prepare its snapshot package. Preparation
reports queued, preparing, ready or failed status. Cancel stops that request;
other requests may continue shared slide preparation. Download opens an
already-ready ZIP and does not start generation. Ready artifacts expire after 30
minutes; prepare again after expiry or failure.

The package contains mission and leg definitions, route KMLs, POIs, retained
planning sources and generated briefing/timeline artifacts. CSV supports data
analysis; customer PDF and PowerPoint support briefings. Use the package
manifest to identify the files actually produced. Do not assume a fixed PDF page
count, workbook sheet arrangement or hand-constructed filename.

The snapshot remains associated with the captured inputs even if the editable
mission changes later. Prepare a new export after corrections. Check UTC timing,
leg order, route maps and transport-state explanations before sharing a
briefing. A document's modeled outage does not establish measured terminal
availability.

The API starts preparation at
`POST /api/v2/missions/{mission_id}/export-preparations`, polls the returned job
at `GET /api/v2/missions/{mission_id}/export-preparations/{job_id}` and
downloads from its `/download` path. See
[mission endpoints](../../api/endpoints/README.md) and
[package import](../mission-package-import.md).
