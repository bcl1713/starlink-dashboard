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

Supported mission/KML APIs seed crossing, no-crossing, anti-meridian, overlapping
SOF/outage and continuation controls. A real 1920x1080 CDP browser exercises
planner, Overview, route-free simulation configuration and mission-clock replay
through production Nginx. No responses are intercepted. Browser provenance is
checked against the installed locked Playwright metadata. Contexts and browsers
close immediately after the journey, including failure.

Actual prepared ZIPs retain stage responses, PDFs, canonical evidence, 240-DPI
color/grayscale rasters and independent full-cell/overflow/geometry checks.
Additional vector checks locate Starshield outline markers, verify page bounds
and reject PoP text within their row. Snapshot/catalog fingerprints and evidence
SHA-256 hashes connect observations to their immutable candidate.

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
