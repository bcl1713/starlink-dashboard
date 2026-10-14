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

Each leg's renderer has one shared 120-second deadline, including layout, maps,
printing, actual PDF verification, and cleanup. Maps retain 40 seconds for
printing and verification; normal work retains three seconds for cleanup. The
Python renderer supervisor has a 130-second emergency limit, and the outer slide
worker allows 180 seconds for captured input preparation plus rendering. These
per-leg limits do not extend the 600-second overall export deadline. Slow cold
exports can still omit the PDF when that overall deadline is exhausted.

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

## Table and timeline presentation

Coordination rows show `HH:MM - HH:MM` in Eastern time. Exact UTC bounds, dates,
seconds and DST offset identity remain in canonical evidence and CSVs. Headers
and timeline axes retain their timing context. Cells stay on one line; rows use
12pt text, reduced as needed to a 9pt minimum without truncation. Inputs that
cannot fit at that minimum still fail the existing overflow checks.

Transport availability uses the same blue as SOF/AR blocks. Gray hatching means
an unavailable transport, `?` means unknown, and a dashed border marks an
operating constraint on an available transport. The table names the affected
transport. Planning interval reasons apply to the mission as a whole; only
transport-local constraints qualify an available lane's marker.

## Rendering performance investigation (14 October 2026)

A controlled retained four-leg render (three available maps, seven pages) took
20.8 seconds, used 78.1 CPU seconds across the container, and peaked at 1.59 GB
of cgroup memory. Map stages consumed 13.5 seconds, actual PDF printing 0.26
seconds, and actual PDF verification 1.80 seconds. These are renderer-only
measurements, excluding source capture, background queue wait and ZIP assembly.
They do not establish timings for every mission or a production download SLA.

Detailed map instrumentation measured 10–30 ms for route planning and about
three seconds per map for scene readiness. Chromium uses software WebGL; the
Earth and city-light textures are both 8192 by 4096 pixels. The readiness probe
previously fetched these textures again after the globe loaded them. It now uses
the same TextureLoader cache. A real-browser regression proves one request per
texture, and all three map PNG hashes match the baseline exactly.

Texture reuse alone did not materially reduce latency or peak memory in this
control: 20.6 seconds and 1.58 GB. Omitting all page previews in a diagnostic
copy saved about 1.6 seconds and did not materially reduce peak memory; previews
remain enabled. The main remaining resource cost lies in globe scene readiness,
not PDF printing. Further work should profile texture upload, shader compilation
and software rendering separately, then evaluate reuse across leg preparation.
No texture or output resolution was reduced in this change.

Maps already render directly at the measured printed dimensions using 300 DPI: a
280 CSS-pixel column needs `ceil(280 * 300 / 96) = 875` raster pixels. The
1920-pixel framing reference does not create a 1920-pixel intermediate raster.
Preserve that output density when investigating further improvements.
