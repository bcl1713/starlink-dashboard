# Operator journal production acceptance

Task 9 passed on 2026-10-17 using only synthetic inputs. The tested product
commit is `e8d6d0f88d9c04ed1f757bd378fa32f0980e7e9e`. This report and its
artifacts are a later evidence-only commit; they do not change that observed
identity. Final branch review and required CI on the pull-request head remain
separate delivery gates. No aircraft or hardware power-loss claim is made.

## Candidate and runtime

The runner archived clean committed HEAD, built the existing backend and
frontend Dockerfiles, checked both OCI revision labels, and served the built
frontend through production Nginx. Application source and browser bundles were
not bind-mounted. Only acceptance fixtures/probes were mounted read-only.

- Backend image:
  `sha256:0402000eb5e79ccbfd3b9020ab14f21e5b994e7f258e5ec922eb8da1d63aadae`.
- Frontend image:
  `sha256:6ca6e1c31ffe36306e39d18566fda7ca36ff4696136b1e36490aa5fa523a2b5d`.
- Source archive:
  `1c770f68152221c8029995211def5206e8221901df060c1b9470397fabadea61`.
- Node 22.22.2; Python 3.11; Docker 29.8.1; Nginx 1.31.7.
- Provisioned Chromium build 1243: HeadlessChrome 153.0.8010.12, verified by
  CDP.
- Simulation fixture `synthetic-operator-demo-v1`, Operator clock fixed at
  `2026-10-17T16:00:00Z`; synthetic missions A/B and legs 1/2.

The actor's Docker context/socket was preserved. Rootless Docker did not publish
ports for the internal network. A task-owned loopback byte relay used Docker
exec to reach port 80 inside the actual Nginx container. The HTTP 200 and Nginx
Server header, origin, container, relay command/PID and reap result are in
[ownership.json](ownership.json). Runtime network isolation remained enabled;
browser requests outside the owned origin were blocked. No fixture API response
was fulfilled. Runtime dependencies were provisioned before acceptance.

## Observed behavior

[Browser proof](browser-proof.json) and the desktop/mobile traces cover:

- Late 1430–1442Z observation entered at 1600Z; typo and leg correction; end
  correction 1545→1535; automatic and supplied audit reasons; remove/restore
  with zero dialogs; immutable history and one current row after refresh.
- Two independent browser contexts and a real 409 conflict, retained draft and
  explicit reconciliation against the accepted correction.
- Actual backend 503 from unwritable SQLite files on mobile; retained disabled
  draft; restored permissions and backend reopen; identical body, epoch and
  idempotency key on retry; exactly one persisted receipt and revision.
- A separately labeled browser acknowledgment-loss injection: `route.fetch`
  committed the real backend request before `route.abort` lost its response.
  Exact retry again left one receipt and revision. This is distinct from 503.
- Owned backend restart and both clients reloaded successfully. Desktop and
  mobile Overview, Missions, Configuration and Data Export returned 200 and
  rendered their expected page content. Overview stayed free of journal UI.

[Failure proof](failures.json) records actual disposable-store behavior:

- Process termination before commit left six revisions; retry produced seven.
  Termination after commit left seven; retry still left seven. The committed WAL
  was 49,472 bytes and recovered; both children were reaped.
- A physically filled private 4 MiB tmpfs returned `commit_outcome_unknown`.
  Actual read-only media returned `store_unavailable`. Neither added revisions
  or receipts, and both reopened ready after media recovery.
- Backup H=6, later H=7, explicit restore H=6, rotated epoch and rejected stale
  epoch. Missing database and unsupported schema failed closed.

[Projections](projections.json) include the actual default current/activity
bytes and checksums, separately requested audit, common H, schedule/status
changes, reported versus recorded times, removed activity and association move
boundaries. [Export comparisons](exports.json) show unchanged telemetry ZIP
bytes and capture identities/revisions across journal writes/reopen, plus an
unchanged planning timeline CSV excluding its generated-at header. Telemetry
uses separately generated **synthetic operational-format input**; its `live`
source tag is a format requirement, not a claim about aircraft data. Simulation
was never relabeled and its telemetry export was rejected.

## Checks and commands

All long commands ran through a recorded owner with explicit wall-clock limits,
10-second termination grace and process-group verification. The complete
commands, exit codes and log hashes are in [commands.json](commands.json).

| Check                                             | Observed result                                      |
| ------------------------------------------------- | ---------------------------------------------------- |
| Runner RED before implementation                  | 12 expected failures                                 |
| Latest runner and fixture checks                  | 16 passed, 2.15 seconds                              |
| Focused Operator/continuity/telemetry checks      | 220 passed, 27.83 seconds                            |
| Affected lint-only backend tests                  | 100 passed, 16.19 seconds                            |
| Canonical backend                                 | 3,924 passed, 20 skipped, 578.85 seconds             |
| Canonical frontend                                | 240 files, 1,708 tests; production build passed      |
| Canonical static after lint correction            | Formatting, Ruff, ESLint, docs, links, typing passed |
| Final production browser                          | 1 journey passed, 23.0 seconds                       |
| Final production storage/projection/export probes | Passed                                               |

The canonical backend ran at `e0ccdb3e6ef8785a05b2b4ae6a83d6088d887c32`;
subsequent changes were acceptance harness or documentation only. Its one
warning was the existing Cartopy facecolor warning. Frontend output included
existing satellite.js externalization and chunk-size warnings. Final-head
static/frontend checks are recorded separately after this evidence commit;
required CI still applies to the final PR head.

Reproduction from the clean product commit with provisioned dependencies:

```sh
timeout --kill-after=10s 60m python tools/acceptance/operator-journal/run.py \
  --candidate e8d6d0f88d9c04ed1f757bd378fa32f0980e7e9e \
  --project starlink-operator-362-final6 \
  --evidence /tmp/starlink-operator-362-final6-evidence
```

Use a fresh project/directory for another run. Browser execution uses the owned
production origin and `npx --no-install playwright test` with
`playwright.operator-journal.config.ts`; there is no Vite server.

## Captures, earlier attempts and cleanup

- [Desktop history](desktop-1920x1080.png),
  [mobile 503](mobile-390x844-error.png),
  [mobile landscape saved draft](mobile-844x390-saved.png).
- [Desktop Overview](desktop-overview-baseline.png),
  [mobile Overview](mobile-overview-baseline.png).
- [Desktop trace](desktop-trace.zip), [mobile trace](mobile-trace.zip).
- [Earlier run outcomes](earlier-runs/results.json) retain failed-run traces.
  Run 1 exposed rootless port behavior; runs 2–4 exposed harness selectors and
  probe-user setup. Run 5 passed, then run 6 added mobile baseline coverage. The
  interrupted run-2 ZIP lacked its central directory; its first trace stream was
  recovered as partial JSONL, not claimed as a complete trace.

[Summary](summary.json) and ownership report zero remaining project containers,
networks and disposable volumes; relay/listener removed; children reaped;
private image tags, extracted source/archive and runtime npm cache removed. The
controller-owned venv, Node toolchain and open-PR worktree remain for final
review. Test caches and data are removed after final-head checks.

[Provenance](provenance.json) records source hashes and sanitization. Only local
workspace/home paths were replaced; screenshots and synthetic identities were
retained. No credential/environment dump or raw build logs were included.
[Artifact hashes](hashes.json) describe the published sanitized files.

[Maintenance and backout](../../operations/operator-journal.md) covers explicit
initialization, migration 1, validation/backup, disable-and-preserve rollback,
restore reports and stale-client reconciliation after epoch rotation. Full call
workflows and mission-package integration remain later child deliverables.
