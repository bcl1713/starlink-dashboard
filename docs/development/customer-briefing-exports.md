# Customer briefing exports

The optional customer mission briefing adds a PDF and machine-readable evidence
to the existing mission export ZIP. It defaults off. Legacy PPTX, CSV, JSON,
KML, and import entries retain their existing contracts.

Configuration is `exports.customer_briefing_enabled`, with environment override
`STARLINK_EXPORTS_CUSTOMER_BRIEFING_ENABLED`. Enable it in an isolated
acceptance project to qualify a candidate. Shared production enablement is a
separate decision from shipping the default-off implementation.

When enabled, one immutable snapshot feeds both legacy exports and the customer
document. The PDF contains ordered leg pages and measured row continuations,
with a ceiling of three pages per leg. Times, offsets, seconds, uncertainty, and
restriction semantics come from the canonical projection. Customer tables omit
approximation marks; the footer covers approximate times. Exact UTC bounds and
rounding flags stay in evidence. SOF / AR bands retain exact window geometry,
with event details in the table. Active X-band transitions, manual AR tracks,
and conflicts with AR or Starshield show X-band Down; missing or stale
prerequisites remain uncertain. The renderer does not classify availability or
merge ground gaps.

## Download contract

Included artifacts are:

- `exports/mission/mission-customer-briefing-trial.pdf`
- `exports/mission/mission-customer-briefing-evidence.json`

Both join `file_structure.mission_exports` and its statistics in the version-2.0
manifest. They publish together after every PDF cell, page, font, identity,
hash, and cleanup check passes. An optional failure returns a complete legacy
ZIP without either member or manifest reference. A publication failure discards
the candidate ZIP and rebuilds legacy output from the same captured views.

The endpoint retains HTTP 200, `application/zip`, and the mission ZIP filename
when the optional pair is omitted. Enabled requests receive
`X-Customer-Briefing-Status: included|omitted`; omission also supplies
`X-Customer-Briefing-Warning` with one of `snapshot`, `data`, `page-budget`,
`overflow`, `runtime`, `deadline`, `pdf`, `evidence`, `cleanup`, `publication`,
or `busy`. Disabled requests have neither header. Headers contain no exception
or source details. The dialog keeps omission feedback visible until dismissal
and confirms that legacy documents were downloaded. The existing Blob service
wrapper remains available.

## Runtime and build

Build the backend from the repository root with explicit Dockerfile
`backend/starlink-location/Dockerfile` and a full `ACCEPTANCE_CANDIDATE_SHA`
build argument. Its Dockerfile-specific ignore file allows only required backend
and frontend build inputs. Compose and GHCR use this root context; frontend and
GFS worker contexts retain their existing paths.

The image packages Node 22.22.2, locked Playwright/Chromium, the local map
bundle, DejaVu Sans fonts, Poppler, and the APO asset. Renderer modules, browser
binaries, map assets, and the APO asset live under `/opt/customer-briefing`,
outside the development `/app` mount. Application commands still run as
`appuser` through the existing entrypoint. Compose uses an init process to reap
orphaned children.

One API process admits one optional renderer at a time, without queuing another
renderer. Busy requests receive legacy output. Blocking builders run outside the
event loop. Disconnect and task cancellation signal the worker and await its
cleanup; ZIP responses close their streams even when sending fails.

The mission render owns one browser, listener, contexts, verifier processes, and
one shared 60-second deadline. Map cutoff preserves the remaining work/cleanup
reserves. Actual-PDF verification and cleanup consume that same allowance. The
application's emergency 70-second wall guard and termination grace force
failure; they cannot qualify a render that exceeds 60 seconds.

Nginx allows 120 seconds of upstream inactivity only for
`/api/v2/missions/{mission_id}/export`. Legacy building precedes optional
rendering, so the request must allow both that work and bounded failure cleanup
before returning its ZIP. Other API routes retain Nginx's 60-second default.
Forwarding, security headers, and the mission-import upload limit remain intact.
This scoped adjustment followed independent review of a measured production 504
at 60.061 seconds during the controlled print-hang deadline check.

Private staging records root/browser/worker process IDs, process groups, and
kernel start identities. Forced cleanup signals only verified owned processes.
Successful process cleanup precedes staging deletion and paired publication. If
cleanup is blocked, the backend logs the retained ownership record path for
operator inspection. Temporary HTML, previews, logs, and ownership files never
enter the ZIP. Evidence retains map-input reasons and canonical row mappings;
diagnostic hashes do not imply diagnostic files were delivered.

## Acceptance boundary

The two accepted checkpoint samples do not accept continuation pages or real
exports. Production qualification must inspect enabled, disabled, omitted,
concurrent, and disconnected requests through the actual API/Nginx/browser path,
including legacy equivalence and ZIP import. New dense and multi-leg PDFs
require explicit customer acceptance. The reviewed export-route timeout
adjustment passed production HTTP 200 deadline-omission ZIP qualification at
76.73 seconds, with complete legacy content, safe headers, unchanged source
inputs and owned cleanup.
[Production samples and validation scope](../samples/customer-briefing/production/README.md)
record the user's 2026-10-09 acceptance of the presented three PDFs and
production download behavior. Shared production enablement remains separate.
