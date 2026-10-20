# Operator acceptance ownership fix

Replacement production acceptance passed on 2026-10-17 for product/harness SHA
`3b033fd13fdfcb2c0abd7bf9a5d464707afd8af4`. This directory is a later
evidence-only addition. The previous reviewed evidence remains in the parent
directory; required CI still applies to the final pull-request head.

The runner now reserves a project across local processes using a Linux abstract
Unix socket. While holding that reservation, it rejects occupied project
containers, networks, volumes and private image tags before build/startup or
cleanup admission. Rejected runs cannot invoke Compose teardown. The reservation
is held until cleanup finishes and is released automatically on process exit.
This addresses the confirmed foreign-resource deletion path without changing
application behavior. The reservation requires Linux, matching this acceptance
environment.

Five new ownership regressions failed before implementation, then passed:
occupied container, network, volume, image and concurrent process reservation.
The combined ownership, runner, fixture and typing-policy suite passed 24 tests
in 2.15 seconds, including safe early failure on an unoccupied project.
Black checked 15 files, Ruff passed, and candidate typing-policy validation
against the reviewed base returned no violations. Complete commands and exits
are in [commands.json](commands.json).

The exact committed candidate was archived and built with the existing
production Dockerfiles. [Summary](summary.json) records both image IDs and OCI
revision labels, source archive checksum and all passing qualification results.
The real Nginx/API browser journey passed in 22.8 seconds, including desktop and
mobile baseline pages, actual SQLite 503 recovery, separately labeled response
loss, exact retries and persisted-count checks. Storage, projection and export
probes all passed. Runtime inputs remain synthetic; operational-format telemetry
is separately generated synthetic input, never relabeled simulation.

[Ownership](ownership.json) records the initial empty-resource inventory,
reservation admission/release, Nginx origin traversal and teardown. No project
containers, networks, disposable volumes, private image tags, process groups or
listener remained. Extracted source/archive and runtime npm cache were removed.
The final host audit and removal of test roots/raw evidence are recorded in the
ignored task fix report after artifact hashes are verified.

The minor gap in explicit pending/saved accessible-status assertions remains
deferred; existing error-state assertions remain covered. The previously
reported Cartopy and frontend build warnings remain disclosed. Full backend and
frontend suites were not repeated for this harness-only fix. The previous
final-head static attempts remain externally blocked by existing adsb.lol link
timeouts; this report does not claim those checks passed on the new head.

[Browser proof](browser-proof.json), [failures](failures.json),
[projections](projections.json), [exports](exports.json),
[desktop trace](desktop-trace.zip) and [mobile trace](mobile-trace.zip) preserve
the new run. [Provenance](provenance.json) records raw source hashes and local
path sanitization. [Hashes](hashes.json) describe these sanitized artifacts.
