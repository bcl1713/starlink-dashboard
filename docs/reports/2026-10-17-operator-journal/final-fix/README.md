# Operator journal final feature fixes

Production acceptance passed on 2026-10-17 for exact product/harness candidate
`b67108909c9a2bac180ff04c03eb79bad6392a82`. This directory is a later
evidence-only addition. Required CI applies separately to the final PR head.

The editor pins its original store ID, API epoch, source mode and simulation run.
A ready-to-ready identity change retains drafts and blocks writes until explicit
reread/reconciliation. Lists and history use identity-specific caches. Revision
history exposes actual/planned UTC times, precision, end state, mission/scope/leg,
retained associations, author and provenance. Save feedback is an accessible
live status and clears when a new editor is opened.

Eight initial regressions failed before implementation. The full frontend suite
then passed 1,717 tests across 242 files. After the small saved-cue follow-up,
all 34 focused tests and the production build passed. Scoped ESLint, formatting,
filename conventions and candidate typing-policy checks passed. Exact commands,
limits, exit codes and process ownership are in [commands.json](commands.json).
The backend was unchanged, and its full suite was not repeated.

[Summary](summary.json) records the archived candidate, source checksum,
production image IDs and matching OCI revision labels. The real production
Nginx/API browser journey passed in 22.3 seconds. It held an actual successful
backend response to assert Saving, then released that same response and asserted
Saved. This response transport interception supplies no fixture data. The
browser inspected the old/new 15:45-to-15:35 UTC end times and leg-1-to-leg-2
values in separate history revisions. Desktop/mobile, conflict, real SQLite 503,
exact retry, restart persistence and existing baseline checks also passed.
[Browser proof](browser-proof.json) records those observations; [desktop
trace](desktop-trace.zip) and [mobile trace](mobile-trace.zip) retain the journey.
Storage-failure, projection and export probes all passed.

The first run on `5bc08bc0` failed after the successful first save because the
new helper removed page interception during the acknowledgment's follow-up read.
A duplicate route continuation failed inside Playwright. The corrected helper
holds only its first mutation and remains registered until context close.
[Earlier summary](earlier-run/summary.json), [browser log](earlier-run/command-018.log)
and the recovered [partial trace](earlier-run/desktop-trace.partial.jsonl)
preserve that failed run. It is not presented as passing evidence.

[Ownership](ownership.json) records private-project admission, runtime commands,
Nginx traversal and teardown. Both runs removed their containers, networks,
disposable volumes, private image tags, process groups and loopback listeners.
Extracted source/archive and runtime npm cache were removed. An independent host
cleanup audit is retained in the ignored final-fix report.

All inputs are synthetic. Existing Cartopy, satellite.js and bundle-size warnings
remain. Existing adsb.lol and NASA link-check timeouts are separate from these
checks; no external retry loop was run. [Provenance](provenance.json) records raw
artifact hashes and local-path sanitization. [Hashes](hashes.json) covers the
sanitized artifacts. Previous accepted evidence remains in the parent directory.
