# Documentation refresh after v1.0.0

## Scope

Reconciled current documentation with `origin/dev` at `dfcf4373`, using the
`v1.0.0` release tag (`3728280a`) to distinguish released behavior from later
integration work. This is a documentation change, not an application release.

| Area                                                | Audit basis                                                                                               |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Installation, configuration, storage and deployment | Compose files, `.env.example`, config models, Portainer template and Dockerfiles                          |
| Operator features, missions and routes              | Frontend controls, Mission/MissionLeg models, import/export handlers, KML parser and ETA services         |
| API and client examples                             | Registered routes, Pydantic request/response models and actual handler behavior                           |
| Monitoring                                          | Metric definitions, health implementation and Prometheus scrape/rule configuration                        |
| Contribution and testing                            | `tools/verify`, CI jobs, tracked runtime selections and workspace workflow                                |
| Historical records                                  | Dated reports/specifications retained as candidate-specific evidence, with clear current-guide navigation |

The README and indexes now point to maintained guides. Obsolete duplicate
walkthroughs retain their URLs as concise links to canonical guidance. Old
assistant instructions and benchmark results are marked historical; absent
assistant packages are not represented as installed tooling.

## Material Corrections

- Removed Phase 0/0.2.0 project-status claims and placeholder clone
  instructions.
- Separated post-release SIGMET and ordinary-itinerary behavior from v1.0.0.
- Replaced retired Grafana operator instructions with native Mission Planner
  guidance while accurately identifying the remaining legacy HTML pages.
- Corrected live-mode behavior, actual configuration fields, environment
  recreation, storage ownership and destructive recovery advice.
- Corrected complete configuration replacement semantics, POI response envelopes
  and empty DELETE responses, route examples and error handling.
- Reconciled editable missions, retained source revisions, package collision
  cloning, inactive imports, and immutable export preparation.
- Removed unverified fixed performance/capacity promises and clarified the
  difference between service health, dish connectivity and data freshness.

## Implementation Limitations Found

These are documented rather than changed by this documentation-only PR:

- Backend root/health/OpenAPI/service metadata still contains a hard-coded
  `0.2.0`; use the release tag or image revision to identify a deployment.
- Bundled mission alert rules filter on a `status` label absent from
  `mission_next_conflict_seconds`; verify rules and delivery before relying on
  automated mission alerts.
- The Portainer template does not forward the documented optional history
  environment overrides unless deployment configuration is extended explicitly.
- Coordinate-only runtime consumers retain repeated-route occurrence limits.

## Validation Boundary

Documentation checks cover Markdown syntax, local link targets and fragments,
filename conventions and existing documentation-contract tests. Examples were
checked against implementation; this sweep does not claim a fresh live-dish,
upstream-provider, container-deployment or rendered-browser acceptance run.
External-site availability is outside the local-link check. No runtime services
were started for this task.

## Verification Results

- Markdownlint: 423 Markdown files, zero errors.
- Local links with fragment checking: 1,106 valid targets, zero errors; 200
  external/example targets excluded by the offline check.
- Existing documentation, link-checker configuration and
  acceptance-documentation tests: 1,288 passed.
- Filename conventions and `git diff --check`: passed.
- Independent review verified release boundaries, runtime versions, API
  replacement semantics, POI envelopes/204 responses and ETA contracts; reported
  material findings were corrected.

Full application test suites and browser acceptance were not rerun because no
application code, dependencies, deployment configuration or UI assets changed.
