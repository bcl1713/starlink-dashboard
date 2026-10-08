# Customer briefing phase-one acceptance

Task 6 verifies the parallel trial. The flag remains off by default. This runner
cannot merge, promote the trial, replace legacy exports, or start phase two.

From the clean feature worktree, run with its full committed SHA:

```sh
./tools/acceptance/customer-briefing/run.sh \
  --sha "$(git rev-parse HEAD)" \
  --evidence /absolute/path/to/new/durable/evidence \
  --task-root /tmp/new-customer-briefing-task-root \
  --profile /absolute/path/to/provisioned-platform-descriptor.toml \
  --existing-package /absolute/path/to/existing-local-mission.zip
```

The optional existing-package input is anonymized locally: human labels and IDs
are replaced, free-text metadata is removed, and KML timing is retained. Its
geometry remains private local review evidence and is never committed.

The evidence and temporary roots must be new and disjoint. Existing project
resources and image tags are refused. The SHA must match clean tracked HEAD.
Production builds use a Git archive, the production Dockerfiles, and production
Nginx. The project name includes the SHA; only Nginx binds a loopback port
(default 15309). All application data lives in private disposable volumes.
`DOCKER_HOST`, context, credentials, proxy and CA configuration are preserved.
Run through an approved host command when the sandbox cannot access Docker. The
outer wall limit is 45 minutes with a ten-second forced-termination grace.

`--check` validates the candidate and port without launching resources.
`--api-only` explicitly records browser acceptance as environment blocked. It is
a diagnostic option, not completion of the UI gate. Branch code must not install
or substitute an acceptance browser. The repository default descriptor is an
unprovisioned template; supply an existing provisioned platform authority.

The backend observation harness runs the production application, routes and
exporters. It records capture fingerprints, preparation origins, map readiness,
renderer identities and stage times. Startup-selected faults exercise projection
failure, invalid PPTX, unavailable browser, texture error, exhausted deadline,
all map options failing and a slow renderer. It never intercepts an export
response or replaces a successful export with fixture bytes. UI journeys connect
only to the platform-owned CDP session, download the real ZIP and check warning
persistence. Normal API imports/exports use rate limits and wait on HTTP 429.

The runner preserves two explicitly different evidence sets:

- `enabled/`, `disabled/` and `fault-*/`: normal source imports and HTTP exports
  through Nginx with production timeline rebuilding. These prove deployed
  behavior and source preservation. Missing coverage prerequisites may correctly
  yield uncertainty rather than synthetic all-Up predictions.
- `canonical/`: committed canonical fixture snapshots injected only at capture
  for exact F01–F10 semantic/deck comparisons. F07 has three clock variants; F08
  has three independent legs. Route identities are namespaced by leg to package
  the fixture's differing route geometries. These pairs exercise the production
  exporters/builders/runtime but do not qualify the normal capture/rebuild path.
  The unchanged fixture assertions run separately under pytest.

The v2 application has no single-leg HTTP export route. `direct/` exercises the
preserved legacy single-leg builder in the production image with the flag both
off and on; it does not claim an HTTP download route exists.

Every extracted deck is retained. `review/` contains representative pairs,
actual PDF renders, full-resolution color/grayscale pages and contact sheets.
Rendering runs offline in an acceptance-only image with pinned LibreOffice and
Poppler packages, a private profile and per-command limits. XML/object
inspection and LibreOffice opening are separate from desktop PowerPoint edit
compatibility.

Ownership records precede launches and retain commands, PID/PGID, limits,
project, volumes, paths and image identities. EXIT/INT/TERM paths reap process
groups and remove only owned containers, networks, disposable volumes and image
tags. `cleanup.json` records filtered Docker inspections and listener checks.
After a forced outer termination, use `resources.json` and the archived Compose
file to verify/finish scoped cleanup before retrying. Preserve evidence and the
open PR worktree. Do not use Docker prune or broad process termination.

Before calling Task 6 complete, run the canonical static/backend/frontend gates,
fixture and runner tests, map asset build, fixed-clock baseline comparison, the
production runner and exact-head CI. Inspect rendered color/grayscale pages and
record observations. Keep blocked or missing checks visible in the review
report.

Desktop PowerPoint editing and customer scan tasks remain manual gates. Record
the reader version, an offline title/table edit and customer time-to-answer for
reduced redundancy, complete outage, remaining transports and SOF/AR. A few
seconds is the target, not a measured result. Explicit customer acceptance of
layout/semantics is required before phase two; legacy replacement requires a
separate decision.
