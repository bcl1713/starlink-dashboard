# Customer briefing production acceptance

The customer PDF remains off by default. PR #312 accepted only the two committed
single-page examples. Dense, continuation and multi-leg documents require fresh
customer acceptance; production download behavior has its own acceptance gate.

From a clean, committed feature worktree, run:

```sh
bash tools/acceptance/customer-briefing/run-production.sh \
  --candidate-sha "$(git rev-parse HEAD)" \
  --evidence-root .superpowers/sdd/customer-briefing-production-acceptance
```

The runner archives the exact candidate, builds both production Dockerfiles with
`--no-cache`, verifies image revision labels and records image IDs. It uses the
actor's configured Docker daemon and proxy/CA trust. Images, source archives,
commands, process groups, Compose project and private volumes are recorded
before launch. Its final cleanup removes only its owned resources and checks the
loopback listener. Failed cleanup keeps the ownership journal and blocks
success.

`--images-only` limits the run to fresh image construction and a runtime probe.
That probe checks the non-root entrypoint, pinned Node, embedded fonts,
installed map assets, Poppler and an actual Chromium launch. Image qualification
alone does not establish production export acceptance.

Full production qualification must seed supported mission/route/provider inputs,
download actual ZIPs through the production Nginx image, inspect every PDF cell,
retain map-input diagnostic reasons, and compare legacy content. It must cover
enabled, disabled and omitted downloads, dense and five-leg missions, failure,
concurrency and disconnect cleanup, three cold timing/determinism controls, and
rendered-browser dialog behavior. Synthetic provider fixtures must be labelled;
immutable composition DTOs cannot substitute for production source capture.

Any export-route proxy timeout change requires measured request evidence and
review before implementation. Shared production enablement is a separate
decision. Preserve evidence outside a feature worktree before its eventual
post-merge removal.

## Qualified implementation and customer review

[Production samples and provenance](../samples/customer-briefing/production/README.md)
contain actual two-/three-page continuation PDFs, a five-leg PDF and real
browser omission feedback. The 19 source scenarios, three cold repeats,
included/off/ omitted browser journeys, concurrency, disconnects and bounded
failure controls passed at `960ae0ba`; both actual production ZIP imports passed
at `aa64cc9f`. Source and resolved runtime equivalence is recorded. The
timestamp comparator normalizes equivalent UTC encodings while retaining exact
instants and all fields; free-form metadata remains verbatim.

The baseline overall runner stopped on that comparison, and a redundant final
whole-matrix rerun was cancelled at the user’s request. Neither is relabelled as
a standalone full-matrix success. Combined qualification has explicit SHA/scope
provenance and all owned resources were removed. On 2026-10-09 the user replied
"Looks great" directly to the request to accept the presented three PDFs and
production download behavior for PR #314. The sample manifest records that
acceptance scope; historical pending flags are superseded. Shared production
enablement remains a separate decision.

## PR323 itinerary controls

Run each private-input control from a clean committed worktree with an isolated
project, unprivileged port and new evidence directory:

```sh
bash tools/acceptance/itinerary-planning/run.sh \
  --project pr323-repairs-SHA12-offline-1 --port 15422 \
  --network-mode offline --input-root /path/to/private/immutable-inputs \
  --evidence /path/to/private/offline-evidence
```

Repeat with a distinct project, port and directory for `online`. Replace SHA12
with the actual candidate's first twelve hexadecimal characters. Inputs are the
original itinerary, three KMLs and retained package; hash readback guards them
before and after execution. Four authorized diagnostic satellites are synthetic
and do not represent operational coverage. Customer briefing enablement is
scoped to the disposable acceptance project.

The browser records explicit action categories, actual preparation stages,
mission-list counts and final inactive reviewed-input readback. Two-second
probes target the backend health listener, status and mission endpoints. Actual
ZIP PDFs must contain route and airport overlays for all three original routes,
with scene identity and PDF-image pixels checked independently. Fresh offline
and online runs use equivalent inputs and monitoring load; timing differences do
not by themselves establish network causation. Preserve failures and inspect
cleanup receipts before retrying. Brian's rendered-journey review remains a gate
before closing the associated issues.

## Prepared PDF resource controls

For the customer PDF sizing and reuse change, use the current preparation API:

```sh
bash tools/acceptance/customer-briefing/run-production.sh \
  --candidate-sha "$(git rev-parse HEAD)" \
  --pdf-resources-only --evidence-root /path/to/private/resource-evidence
```

This mode builds fresh exact-SHA production images, seeds supported source
scenarios, records preparation stages, downloads ready ZIPs through Nginx, and
independently checks delivered PDF resources, canonical cells and page geometry.
The three-leg resource fixture has five pages and distinct maps; its ready job
must reuse the same ZIP and preparation ID. Run the private offline and online
itinerary browser controls above separately. The historical full matrix's
blocking `POST /export` assumption predates the current preparation API and
cannot qualify that API by interpreting its job JSON as a ZIP.
