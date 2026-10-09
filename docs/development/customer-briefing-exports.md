# Customer briefing exports

The customer PDF is exported as `exports/mission/<mission-name>-brief.pdf` (for
example, `exports/mission/27-02-brief.pdf`). Path separators and unsafe filename
characters are replaced with underscores. Long names are capped at 240 UTF-8
bytes before the suffix; an empty name uses `mission`.

Customer PDFs are enabled by default through
`exports.customer_briefing_enabled`. Set
`STARLINK_EXPORTS_CUSTOMER_BRIEFING_ENABLED=false` to opt out explicitly.
Mission ZIPs contain saved mission/leg data, routes, POIs, per-leg and combined
CSVs, and the customer PDF with machine-readable evidence. They contain no
PowerPoint files. The standalone leg export API remains compatible.

Successful saves invalidate affected PDF pages without waiting for rendering.
One elected background coordinator prepares each leg from captured committed
inputs. New inputs cancel obsolete workers and browser descendants;
token-checked publication prevents stale results. Unchanged legs reuse their
current pages. Route, POI, satellite, coverage, template, and asset changes are
reconciled periodically and before export. Leg composition changes regenerate
affected numbered headers.

The SQLite store is `data/missions/.slide-cache/slides.sqlite3`, outside mission
import/export data. It survives restarts with the existing missions mount. A
coordinator lock prevents duplicate dispatch across API processes; a worker lock
protects restart cleanup. Startup requeues interrupted work and backfills older
missions. Only current artifacts are retained. Export copies cached bytes in a
consistent read, so replacement and deletion cannot invalidate an active
download.

Ready exports merge existing pages and evidence and use prepared snapshots for
CSVs. They do not rebuild timelines, render maps, or launch browsers. Cold
exports wait for background preparation, up to 600 seconds; the production proxy
allows 660 seconds for this endpoint. A new save while waiting follows current
inputs. An export already assembling retains its captured revision.
Disconnecting the request stops its wait while shared preparation continues.

A failed customer PDF leaves mission data and CSVs available with a safe
omission warning. A subsequent export retries failed preparation. Explicitly
disabling background tasks prevents new rendering; available ready artifacts can
still be used, otherwise the PDF is omitted. Service shutdown cancels and reaps
owned workers and browser processes.

Evidence keeps schema version 2 and its ordered legs/pages. Its `render` object
uses schema version 3 with `mode: cached-page-assembly`, zero browser launches,
the assembled PDF hash, rebased page proof, and each qualified fragment's
original render report. The APO JPEG is circularly clipped in the PDF layout to
remove its white corners without changing the artwork.

Verify background delivery against committed production images:

```bash
timeout --kill-after=10s 75m python3 \
  tools/acceptance/customer-briefing/background.py \
  --candidate-sha <HEAD-SHA> --evidence-root <private-directory>
```

The runner owns an isolated Compose project, compares ready exports with full
rendering, checks supersession and restart reuse, verifies actual PDF geometry
and raster output, downloads through the browser, and removes its containers,
networks, private volumes, and image tags.
