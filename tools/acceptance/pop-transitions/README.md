# PoP transition production acceptance

From a clean committed feature worktree, using Python 3.11, Node 22.22.2 and
locked frontend dependencies, run:

```sh
timeout --kill-after=10s 45m python3 tools/acceptance/pop-transitions/run.py \
  --candidate-sha "$(git rev-parse HEAD)" \
  --evidence-root /path/to/new/private/pop-evidence
```

The actor's configured Docker context, proxy, CA trust and credentials are
preserved. Production backend/frontend Dockerfiles build without cache from an
exact Git archive. Revision labels and content image IDs are checked before a
private Compose project starts. Its volumes, image tags, loopback listener,
commands and process groups are journaled before launch. Exit and signal cleanup
remove owned runtime resources and retain the cleanup receipt, logs and hashes.

Supported mission/KML APIs seed crossing, no-crossing, anti-meridian,
overlapping SOF/outage and continuation controls. A real 1920x1080 CDP browser
exercises planner, Overview, route-free simulation configuration and
mission-clock replay through production Nginx. Those primary checks do not
intercept responses. A separate labelled browser control intercepts status
responses with synthetic early/late/mismatch evaluator results to check
presentation only. Browser provenance is checked against the installed locked
Playwright metadata. Contexts and browsers close immediately after the journey,
including failure.

Actual prepared ZIPs retain stage responses, PDFs, canonical evidence, 240-DPI
color/grayscale rasters and independent full-cell/overflow/geometry checks.
Additional vector checks locate Starshield outline markers, verify page bounds
and canonical UTC x-position/width and reject transition text within their row.
The table event is exactly `Starshield Transition Window` and the outlined
legend is `Starshield Transition`; event cells keep the established one-line
layout and all fit limits. Snapshot/catalog fingerprints and evidence SHA-256
hashes connect observations to their immutable candidate.

Early/late/mismatch cases are explicitly labelled deterministic provider
fixtures through the shipped evaluator. They are separate from the actual HTTP
simulation observations. Neither category claims measured operational Starshield
handover timing. Actual service availability and preference remain governed by
the existing transport logic.

Focused runner tests cover dirty/mismatched candidates, image identity,
wall-clock failure termination and teardown after browser/PDF failures:

```sh
timeout --kill-after=10s 5m uv run \
  --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_pop_transition_acceptance.py -q
```

Conditional controls use the shipped planning capture and route-acceptance
services inside the actual candidate image. Captured route, satellite, coverage,
constraints and evaluation context are then persisted through the ordinary leg
API. The sole-Starshield, Ka-alternative, concurrency-only X and concurrency
plus independent elevation controls assert 600/0/0/600 seconds respectively. A
Ka recovery at the crossing asserts 300 seconds; an unspecified X capability
remains unresolved. The replay verifies that the Prefer Starshield policy keeps
X offline through fallback windows: qualification does not activate another
transport.

Each conditional mission has a visible planner screenshot and an actual prepared
PDF. The PDF probe independently measures hero-band colors, the physical
Starshield lane, canonical outline geometry and the exact short legend above the
coordination table. Every measured table cell must remain one line. Dense
continuation pages retain the existing complete-cell, font and fit checks. The
actual normal/dateline/route-free simulation responses remain separate from the
explicitly intercepted early/late/mismatch presentation fixtures.

Physical replay is compared at the HTTP response's exact mission clock against
actual-image prepared replay frames. This differs from the saved planner's
availability projection: legacy concurrency advisories can retain planner X
availability, and the replay retains terminal physical landing blackouts. A
second preparation with an unavailable PoP catalog must produce identical
physical events. The captured planning transport configuration and Starshield
preference must also remain unchanged after replay; a physical X capability
value does not imply operator activation.

Normal replay runs for 300 seconds so the real active-window Overview can be
captured with its active UI status visible before and after the screenshot.
Browser commands have a 480-second bound; per-test deactivation and
worker-specific response evidence preserve cleanup and failures. Independent PDF
checks continue after a browser or another PDF failure, with per-check failure
JSON and incremental `qualification-results.json`. Any failed check still fails
the overall runner.
