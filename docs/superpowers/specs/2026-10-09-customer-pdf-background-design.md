# Customer PDF background preparation

Customer PDFs are enabled by default. Mission ZIPs contain mission data, routes,
POIs, CSVs, and the customer PDF with its evidence; they contain no PowerPoint
files. The user explicitly limited background generation to customer PDFs.

Successful persisted saves invalidate changed legs without waiting for
rendering. A durable SQLite cache stores desired inputs and completed per-leg
PDFs. One coordinator holds a filesystem lock across API processes and
dispatches one owned, time-limited Python child at a time. That child prepares
the immutable timeline snapshot and uses the existing qualified browser
renderer. Superseding inputs cancel the child and its browser descendants.
Token-checked transactions prevent late publication. Unchanged legs keep their
completed artifacts.

Reconciliation captures route, POI, coverage, satellite, constraint, and saved
leg inputs without rebuilding timelines. It runs after saves, on startup,
periodically for dependency changes, and before exports. Renderer and asset
changes invalidate the cache. Leg numbering is part of render identity, so
composition changes regenerate affected headers. Deleted legs cannot publish or
recreate artifacts.

An export waits for current background work and captures all ready records in
one consistent read. It merges PDF pages in leg order, remaps evidence page
numbers, and uses prepared snapshots for CSVs. The ready export path never
builds timelines, maps, or slides. An export already assembling keeps its
captured revision; pending exports follow new saves. Disconnecting an export
stops its wait without canceling shared background work. Failed PDF generation
preserves data and CSV delivery with the existing safe omission warning; a
subsequent export retries failed preparation. Disabled PDFs produce data and
CSVs only.

Cached bytes are read transactionally into export-owned memory, avoiding file
deletion races. Only the current revision is retained. Shutdown cancels and
reaps workers; restart requeues interrupted work. The JPEG APO patch is
circularly clipped by CSS to hide its white corners without editing brand
artwork.

Verify superseding saves, unchanged-leg reuse, deletion, restart, duplicate
coordinators, dependency invalidation, snapshot consistency, page/evidence
order, absence of PPTX files, no heavy ready-export calls, and rendered logo
appearance. Measure cold preparation versus ready export on identical
representative inputs.
