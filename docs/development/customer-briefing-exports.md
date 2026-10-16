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

Transport lanes use the same dark blue as SOF/AR blocks when unavailable and
the same light background when available. They have no hatching, Up/Down text,
or separate key; `?` still identifies unknown availability. X/Starshield
concurrency evidence names the conflict in the table and labels the X lane
where space permits. A released concurrency conflict does not override another
independent X outage. Generic internal notes on available transports do not
create customer "operating constraint" rows.

Planning Ka events and POIs use the captured coverage on the original minute
grid, matching the planning outage calculation. Recalculating coverage edges
on the expanded X planning grid previously shifted those events by seconds,
creating misleading available-with-note intervals beside real Ka outages.

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

## PoP coordination windows

Customer briefs capture the validated PoP catalog and its fingerprint with the
other immutable preparation inputs. Detached render workers use that capture; a
changed catalog invalidates preparation through the normal publication guard. An
invalid or unavailable catalog never produces a silently reduced forecast.

Starshield outlines contain no text labels inside the timeline row. The
coordination table uses the existing compact Eastern-time cells and clock/axis
context, retaining exact UTC bounds in machine evidence. Overlapping SOF, outage
and PoP impacts remain together. Physical transport decisions remain unchanged;
the call assessment can show a planned communications outage, coordinated X-Band
fallback, an alternative transport, or unresolved capability. Full canonical
windows remain intact when display edges are clipped.

The full ten-minute window counts as a planned outage only where no usable
alternative exists. Ka recovery splits the assessment at its exact UTC bound.
Concurrency-only X can be a fallback; an independent AR or geometry block
prevents that classification. Fallback requires coordination and never activates
X automatically. Missing or stale capability evidence remains unresolved.
Existing confirmed outages and transition outages use union accounting. The
physical Starshield lane can remain connected throughout a planned call outage.

The Event / impact entry reads exactly “Starshield Transition Window”; the
outlined legend reads exactly “Starshield Transition”. Event cells retain their
existing one-line layout, including combined SOF/outage impacts. Measured
whole-row pagination, fonts and PDF text/geometry validation remain unchanged.
Continuation pages retain the explanatory note and measured whole-row layout.
Catalog editing and discovery management screens remain outside this feature.

Run the exact-candidate production control described in
[PoP acceptance](../../tools/acceptance/pop-transitions/README.md) to verify
real Nginx/API browser journeys and actual delivered PDF cells, outlines and
rasters.
