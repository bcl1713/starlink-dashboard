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
commands, process groups, Compose project and private volumes are recorded before
launch. Its final cleanup removes only its owned resources and checks the
loopback listener. Failed cleanup keeps the ownership journal and blocks success.

`--images-only` limits the run to fresh image construction and a runtime probe.
That probe checks the non-root entrypoint, pinned Node, embedded fonts, installed
map assets, Poppler and an actual Chromium launch. Image qualification alone
does not establish production export acceptance.

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
