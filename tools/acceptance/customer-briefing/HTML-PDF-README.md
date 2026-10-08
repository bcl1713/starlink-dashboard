# HTML-to-PDF visual checkpoint

Execute only the two examples approved in PR #312. This developer runner does
not change production exports, Dockerfiles, ZIP manifests, API or UI behavior.

Start from clean committed HEAD on the isolated feature branch. Use the actor's
configured Docker socket and preserve proxy, CA and registry configuration.

```bash
timeout --kill-after=10s 45m python3 tools/acceptance/customer-briefing/html_pdf_checkpoint.py \
  --candidate-sha "$(git rev-parse HEAD)" \
  --evidence-root .superpowers/sdd/2026-10-08-customer-briefing-html-pdf/evidence/build \
  --build-only
```

Use the returned exact revision image tag for the isolated run:

```bash
timeout --kill-after=10s 15m python3 tools/acceptance/customer-briefing/html_pdf_checkpoint.py \
  --candidate-sha "$(git rev-parse HEAD)" \
  --evidence-root .superpowers/sdd/2026-10-08-customer-briefing-html-pdf/evidence/run \
  --image-tag <returned-tag> --runtime-tests
```

The runner verifies image revision, creates a private Compose project and
volume, runs with no external network or published host ports, and removes
containers and disposable volumes in `finally`. Browser contexts, process
descendants and loopback listeners close before each render reports success.
Recorded commands have wall-clock guards; successful rendering additionally
requires one shared 60-second monotonic deadline, including teardown.

Each delivered directory contains HTML, 3200×1800 preview PNG, one 960×540 pt
PDF and exact evidence JSON. Actual PDF color/grayscale rasters and full
resolution crops live in the retained `raw/renders` evidence. Three cold primary
requests must retain customer text, SVG geometry, decoded preview pixels, page
assignments and normalized PDF structure; only named creation metadata/document
IDs are excluded. The separately rendered incomplete-X example cannot qualify
primary appearance. Missing-map fallback and overlong content are separate
controls.

The runtime manifest labels synthetic immutable DTO injection explicitly. It
records fixtures, lockfile, fonts/assets/browser and OS/Python package
inventory, image revision/ID and stage timings. This checkpoint does not prove
API capture, legacy ZIP equivalence, production Nginx integration or dense
pagination.

`checksPassed` and `visualAcceptance` are separate. Visual acceptance and the
customer scan test remain pending until explicitly reported. Review the actual
PDF and primary page, then identify when capability is reduced, what is lost,
what remains and when SOF/AR applies without further explanation. Record scan
time and accept or revise the hierarchy, four posture colors, typography, table
density, patch and map. Stop here; generalization and integration require that
acceptance and a later implementation plan.
