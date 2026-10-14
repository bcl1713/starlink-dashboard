# Mission export preparation

Mission ZIP exports use explicit preparation. POST
`/api/v2/missions/{mission_id}/export-preparations` returns a job reference;
GET the returned job path for queued/preparing/ready state and DELETE it to
cancel that export's work. Download only through the ready job's `download_url`.
Preparation has a 600-second aggregate deadline; ready files expire after
30 minutes. A saved change supersedes a pending export. A completed download
keeps its labeled snapshot and does not switch to later edits.

Legacy POST `/api/v2/missions/{mission_id}/export` returns 200 for a current
already-ready ZIP, otherwise 202 JSON with a `Location` status URL. Clients
must poll that preparation and then fetch its download, rather than saving the
202 JSON as a ZIP. A cold download never waits for PDF rendering. Cancellation
and download disconnects do not stop shared customer slide preparation.
