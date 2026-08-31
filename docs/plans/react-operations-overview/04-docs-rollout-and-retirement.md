# Phase 4: React Operations Overview Docs, Rollout, and Retirement

> **For Hermes:** Route documentation as an independent workstream, keep the
> implementation PR targeted to `dev`, and do not combine rollout approval with
> the separately gated Grafana-retirement decision.

This phase governs operator documentation, review, deployment, rollback, and the
future removal boundary. The
[master plan](../2026-08-29-react-operations-overview.md) and exact-head
evidence from [Phase 3](03-runtime-and-browser-acceptance.md) remain binding.

## Documentation impact routed independently

Documentation must be reviewed/routed as an independent docs workstream rather
than buried inside a feature commit. It may be a separate docs-only PR targeting
`dev`, linked to the implementation PR, but must merge before operator rollout.
Do not edit these during core code tasks:

- `docs/setup/quick-start.md` and installation verification/access URLs.
- `.env.example` and `docs/setup/configuration/environment-variables.md` must
  unconditionally add `PROMETHEUS_URL`, document default
  `http://prometheus:9090`, state that it is backend/internal-only, and warn
  never to expose it to browser configuration.
- `docs/grafana-configuration.md` and `docs/grafana-dashboards.md` to describe
  dual-run status, **not** retirement.
- `docs/troubleshooting/services/grafana.md` to retain Grafana support.
- `docs/troubleshooting/services/backend.md`, monitoring/data diagnostics, and
  CSP/radar troubleshooting.
- `monitoring/README.md`, `monitoring/docs/README.md`, and
  `monitoring/docs/services-overview.md` for React Overview and Grafana URLs.
- Mission/operator monitoring and incident-response SOPs discovered by a fresh
  link/reference search.
- API documentation/OpenAPI examples for `/api/monitoring/history` and
  `/api/monitoring/ground-entry-point`.

Docs acceptance runs Markdown lint, filename conventions, and link checks:

```bash
pre-commit run --all-files
python -m pytest tools/tests/test_docs.py tools/tests/test_link_checker_config.py -q
python tools/check_filename_convention.py
```

Docs must say `/overview` is the default, list refresh/freshness and clock/radar
controls, explain paused/stale/error states, and state plainly that Grafana is
still deployed during dual-run.

## PR, rollout, and rollback

### PR rules

- Rebase/update from current `dev`; preserve
  `07593c69040ad447000bf526d6453ec5c6faacfa` as an ancestor and resolve drift
  before evidence. If `dev` moved, rerun the baseline contract and all
  exact-head gates after update.
- Open `feature/react-operations-overview` **to `dev`, never `main`**. Verify
  the GitHub PR base explicitly (`gh pr view --json baseRefName,headRefName`)
  and require `baseRefName == "dev"` before review/merge.
- Keep commits at the boundaries above. No generated evidence, unrelated
  formatting, Grafana JSON/service changes, or retirement work.
- Require backend/API, frontend, browser/accessibility, security/CSP, and
  operator parity reviewers. Link the independently routed docs PR.
- Never merge on stale evidence: CI and manual acceptance SHA must equal the PR
  head. Merge to `dev` only after dual-run parity is approved.

### Rollout

1. Deploy to a representative simulation environment with Grafana unchanged.
2. Verify `/` and `/overview`, direct links to all old routes, backend health,
   Prometheus history, CSP, tile behavior, and Grafana availability.
3. Run side-by-side parity and a bounded soak; keep Grafana as the documented
   fallback.
4. Promote the React route as default on `dev` only after evidence passes.
5. Observe API latency/error rate, Prometheus query load, browser
   memory/network, stale frequency, tile failures, and operator feedback before
   any broader promotion.

### Rollback

- Preferred code rollback: revert the overview PR on `dev` and rebuild
  `starlink-location` and `mission-planner` with the required no-cache sequence.
- Immediate operational fallback: navigate operators to Grafana at port 3000; it
  remains deployed and unchanged.
- Verify rollback with health checks, old management routes, Grafana dashboard,
  and absence of `/api/monitoring/*` consumers. Do not delete Prometheus or
  Grafana volumes and do not remove new endpoints independently while the
  deployed frontend still calls them.
- If only radar/ArcGIS is failing, disable radar in the user control and retain
  vector operations; do not roll back telemetry merely for a third-party tile
  outage.

## Separate future Grafana-retirement gate

Grafana retirement is a **new, separately scoped follow-up PR** to `dev`. This
implementation PR must not perform even preparatory deletions. Open retirement
work only after all of the following are documented and approved:

1. Every clock, panel, map layer, filter, threshold, time window, control, and
   accessible alternative has a React equivalent or explicit owner-approved
   retirement.
2. All deterministic states and all six exact viewport sizes pass.
3. Event-driven lifecycle observation across five scheduled one-second refreshes
   plus one actual manual refresh preserves map/chart/filter/focus state and
   correlates every transition to request start/completion. Honest supporting
   capture timestamps and achieved cadence are reported without a minimum-fps
   pass criterion.
4. Existing mission, route, POI, satellite, import/export, and configuration
   workflows are regression-clean.
5. React has no Grafana endpoint, plugin, session, datasource-proxy, dashboard,
   or asset dependency, proven by static searches, a runtime with Grafana
   unavailable, and browser-network assertions forbidding port 3000/Grafana
   paths while React remains functional.
6. A production-representative soak establishes acceptable update latency,
   browser memory/network, Prometheus load, and interruption recovery.
7. Operator sign-off, rollback drill, docs/SOP migration, bookmark/link audit,
   and observability replacement are complete.
8. The team explicitly decides whether retirement covers only Fullscreen
   Overview or every remaining Grafana dashboard; service removal requires the
   latter.

Only then may the follow-up inventory and remove, with test-first deployment
changes:

- `grafana` service and `grafana_data` from `docker-compose.yml`.
- Grafana from `deployment/portainer-ghcr-compose.yml` and publish workflows.
- Any deployment Grafana image/Dockerfile, plugin installation, provisioning,
  dashboards, datasources, custom icons, ports, passwords, and firewall rules.
- Grafana-specific health checks, tooling, tests (including
  `tools/tests/test_fullscreen_overview_dashboard.py`,
  `test_grafana_backend_proxy_runtime.py`, and `test_grafana_compose.py`) only
  after equivalent React/API contracts replace their coverage.
- Setup, verification, troubleshooting, architecture, monitoring, incident, and
  operator documentation.

Prometheus remains. The retirement PR must include its own rollout/rollback,
prove no production references remain, and target `dev`, never `main`. Until
that gate is passed and that separate PR merges, Grafana is the live fallback;
removing it early would convert confidence into theatre, which is rarely an
operational improvement.
