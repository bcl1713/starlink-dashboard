# Customer Briefing Production Integration Tasks

Required Tasks 5–8 companion to the
[production plan](2026-10-08-customer-briefing-production.md). Its constraints,
definitions, verification commands, and approval gate apply. Implementation and
broad acceptance remain pending; native implementation is authorized by the
user's 2026-10-08 approval.

## Task 5: Feed enabled legacy exports from the same captured snapshot

**Files:** Modify `B/app/mission/package/{__main__,__init__}.py`,
`B/app/mission/exporter/{__main__,pptx_builder,snapshot_views}.py`. Create
`B/app/mission/package/snapshot_export.py`. Tests:
`B/tests/unit/{test_export_snapshot,test_package_exporter,test_package_adjusted_export,test_package_export_adjusted_times,test_legacy_compatibility_exports}.py`.

**Interfaces:** Add optional keyword-only `snapshot: ExportSnapshot | None=None`
to `export_mission_package` and snapshot-consuming package helpers. Preserve its
`IO[bytes]` return contract and all existing default callers. `SnapshotViews`
supplies mission, leg, timeline, original KML/route/POIs, private prepared map
POIs, and captured ground-entry data. Create
`build_snapshot_legacy_package(snapshot: ExportSnapshot) -> IO[bytes]`. Add
explicit optional `export_snapshot` injection through CSV/PPTX/map/footer
builders where a manager adapter alone cannot remove live reads. Distinguish
injected absent values from no injection so missing captured data cannot
silently fetch a live replacement.

- [ ] Write `test_enabled_builders_never_reread_after_capture`: mutate mission,
      timeline, route, POIs, catalog, coverage, constraints, and ground-entry
      storage after capture; replace live loader/preparation functions with
      exceptions. Both per-leg/combined legacy and PDF inputs retain the
      captured fingerprint, adjusted departures, splices, clocks, and metadata.
- [ ] Write fixed-clock legacy comparisons between baseline and snapshot-fed
      exports for normal, adjusted, cached-fallback, missing timeline, shared
      route, and AR cases. Compare every CSV/JSON/KML byte and PPTX member XML,
      text, style, media, slide count/order, and dimensions. Exclude only
      identified ZIP timestamps/PPTX creation metadata, with written reasons.
- [ ] Run tests for meaningful RED. Implement optional injection, replacing
      repeated `_load_export_timeline` rebuilds, parent footer/cover reloads,
      cached ground-entry lookup, and map route resolution only when captured
      views are provided. Keep standalone/default exporter behavior.
- [ ] Serialize original mission/leg/KML/POI import data from captured source
      payloads. Use effective routes/private generated POIs only for document
      maps, so adjusted display geometry does not overwrite import content.
- [ ] Assert storage hashes/revisions and prepared timeline publication remain
      unchanged by export. Use fresh model copies per consumer; one builder's
      mutation cannot affect the others. No lock held during browser rendering.
- [ ] Run snapshot/legacy/package/adjusted-time checks and commit
      `feat: share captured inputs across enabled mission export builders`.

## Task 6: Own optional rendering and publish the pair atomically

**Files:** Create `B/app/mission/exporter/customer_runtime.py`,
`B/app/mission/package/customer_artifacts.py`, and
`B/app/mission/package/export_job.py`. Modify
`B/app/mission/{routes_v2.py,package/__main__.py}`, `B/app/models/config.py`,
`B/app/core/config.py`, `B/config.yaml`. Tests:
`B/tests/unit/test_customer_runtime.py`, `test_customer_package.py`,
`test_customer_export_job.py`, `B/tests/integration/test_mission_routes_v2.py`.

**Interfaces:**

```text
CustomerBriefingArtifacts(pdf: bytes, evidence: bytes)
CustomerBriefingOutcome(status: included|omitted, warning_code: str | None,
                         artifacts: CustomerBriefingArtifacts | None)
MissionPackageDownload(stream: IO[bytes], briefing: CustomerBriefingOutcome | None)
render_customer_artifacts(snapshot: ExportSnapshot, *,
                          cancel: threading.Event) -> CustomerBriefingOutcome
build_mission_package_download(mission_id, route_manager, poi_manager, *,
                              enabled: bool, cancel: threading.Event)
                              -> MissionPackageDownload
```

Declare frozen data classes in `customer_artifacts.py`; runtime returns a
qualified pair or a safe omission code. `export_job.py` runs blocking package
work outside the event loop, owns its worker/cancellation event, and gates
optional renderer concurrency to one per API process. Acquire without an
unbounded queue; busy requests use legacy output. Hold the slot until cleanup.

- [ ] Write `disabled_never_captures_or_launches`, `enabled_captures_once`,
      `capture_failure_returns_legacy_warning`, `busy_returns_legacy`, and
      enabled inclusion tests. Assert default false and correct
      `STARLINK_EXPORTS_CUSTOMER_BRIEFING_ENABLED` parsing.
- [ ] Write failures at projection, page-budget, overflow, runtime, deadline,
      PDF, evidence, cleanup, and each ZIP/manifest insertion boundary. Assert
      complete legacy ZIP, neither optional member/manifest reference, correct
      statistics, unchanged manifest version 2.0, and safe omission code.
      Existing legacy package errors still propagate as export failures.
- [ ] Run focused backend tests for RED. Implement private temp staging and
      renderer subprocess ownership with recorded PID/PGID/paths before waiting.
      Run version-2 Node entrypoint and application PDF verifier from installed
      paths; do not import acceptance scripts or fixtures.
- [ ] Validate final report/fingerprint/page plan/PDF verification/hashes and
      version-2 evidence before returning pair bytes. Temporary HTML/previews/
      logs never enter ZIP. Delete temp paths only after descendants are reaped.
      A 70-second emergency renderer wall guard plus 10-second kill grace can
      force failure, but cannot qualify work outside the shared 60 seconds. If
      forced Node termination bypasses its handlers, use its recorded owner file
      to verify and stop only surviving request-owned browser/listener/ verifier
      descendants before considering cleanup complete.
- [ ] Build legacy entries from Task 5 views, then add both pair members and
      manifest entries together. If insertion fails, close/discard that ZIP,
      rebuild the legacy ZIP from those same views, and omit both members. No
      `ZipFile` member deletion or partial pair left in an append-only ZIP.
- [ ] Add configuration `exports.customer_briefing_enabled=false` and its
      environment override. Enabled capture failure uses the original legacy
      package path; successful capture never rereads live sources. Disabled
      requests retain their existing path and file set.
- [ ] Route returns existing ZIP filename/content type and HTTP 200 on optional
      omission. Add `X-Customer-Briefing-Status: included|omitted` only when
      enabled; add `X-Customer-Briefing-Warning` only on omission, using the
      spec's code allowlist. Never put internal exception/source content there.
- [ ] Own the blocking worker using the application's asynchronous request path.
      Signal cancellation on disconnect and await its cleanup; add cooperative
      checks between legacy stages and interrupt owned renderer subprocesses. Do
      not abandon a future/thread after timing out. Close ZIP streams on
      completion, disconnect, and response errors.
- [ ] Exercise concurrent requests, disconnect during map/print/verification,
      cancellation during legacy generation, failed cleanup, and forced renderer
      termination. Verify request-private artifacts do not cross requests and
      worker/browser/listener/process trees are gone before return.
- [ ] Run focused endpoint/package/runtime checks and commit
      `feat: publish optional PDF evidence with safe legacy fallback`.

## Task 7: Ship the renderer and preserve download feedback

**Files:** Modify `B/Dockerfile`, `docker-compose.yml`,
`.github/workflows/publish-ghcr.yml`, `tools/check_publish_ghcr_workflow.py`,
`tools/tests/test_publish_ghcr_workflow.py`. Create `B/Dockerfile.dockerignore`
for root-context builds. Modify
`F/src/{types/export.ts,services/export-import.ts,components/missions/ExportDialog.tsx}`;
tests: `F/src/services/export-import.test.ts`,
`F/src/components/missions/ExportDialog.test.tsx`. Document image paths/config
in `docs/development/customer-briefing-exports.md`. Modify `F/nginx.conf` only
if measured route-specific accommodation is needed.

**Interfaces:** Add
`exportMissionDownload(missionId: string): Promise<MissionExportDownload>`, with
this return type:

```typescript
type MissionExportDownload = {
  blob: Blob;
  briefingStatus?: "included" | "omitted";
  warningCode?: string;
};
```

Preserve `exportMission(missionId): Promise<Blob>` as a wrapper.
Unknown/malformed warning values map to generic safe UI copy.

- [ ] Write build-contract tests for root backend build context, precise
      Dockerfile, revision label, renderer/font/asset packaging, non-root paths,
      and unchanged GFS/frontend build contexts. Update the existing GHCR
      validator's explicit expected backend context, not its safety checks.
- [ ] Write UI/service tests for absent headers, inclusion, omission, unknown
      warning code, download failure, repeated click prevention, timer disposal,
      and URL revocation. Omitted downloads remain visible until dismissal;
      assert successful ZIP download and complete legacy-document copy.
- [ ] Run tests for RED; implement backend root-context multi-stage image. Copy
      locked frontend package manifests, build map entry, install pinned
      Chromium/OS dependencies and fonts/Poppler, then copy only required
      renderer modules, map bundle/assets, and Node into the Python runtime.
      Keep existing backend/PPTX requirements and entrypoint. Do not ship
      frontend node_modules wholesale or acceptance-only dependencies.
- [ ] Update Compose backend `build.context: .` with explicit
      `dockerfile: backend/starlink-location/Dockerfile` and GHCR matrix. Ensure
      runtime files sit outside the development `/app` bind mount. Scope the
      Dockerfile-specific ignore file to prevent credentials, worktrees, private
      evidence, and local dependencies entering the context. Preserve inherited
      proxy/CA and registry credentials.
- [ ] Implement structured header parsing and persistent omission feedback. Show
      “ZIP downloaded. Legacy documents are included; the customer PDF could not
      be included.” plus safe retry guidance. Keep ordinary success behavior,
      dispose timers on unmount/reopen, and revoke download URLs. Do not expose
      renderer mechanics or diagnostic strings in the dialog.
- [ ] Measure combined legacy/render request times through production Nginx,
      including slow bounded omission. If its current timeout truncates these
      valid requests, present measurements and an export-route-only timeout
      proposal for review before applying it. No broad timeout change.
- [ ] Run build validator, UI selection, frontend production build, and clean
      exact-SHA no-cache backend/frontend image builds. Record pinned runtime,
      fonts/assets/lockfile hashes and revision labels. Do not enable shared
      configuration or publish release images as part of this task.
- [ ] Commit `feat: package briefing runtime and report omitted PDF downloads`.

## Task 8: Qualify real production exports and finish delivery

**Files:** Create
`tools/acceptance/customer-briefing/{run-production.sh,production.py,compose.production.yml,production-journey.mjs}`,
`tools/tests/test_customer_briefing_production.py`, and
`docs/development/customer-briefing-acceptance.md`. Acceptance calls application
builders and the production API; it does not replace the endpoint with fixture
responses or monkeypatch the renderer.

- [ ] Write runner lifecycle tests for ownership recorded before launch,
      SIGINT/TERM, timeout, failed image/build/browser, and teardown
      verification. Run RED, implement task-specific
      Compose/loopback/private-volume runner with exit/signal handlers, and run
      GREEN. Use production backend, frontend Nginx, and Prometheus
      configuration; isolate fixture sources.
- [ ] Require clean committed full SHA, image revision/ID checks, and fresh
      production Dockerfile builds. Seed deterministic missions/routes/source
      data using real supported inputs and storage. Label all synthetic provider
      fixtures; capture actual API responses/fingerprint/storage revisions.
- [ ] Through Nginx, run disabled legacy download; enabled successful pair;
      enabled missing-map fallback; incomplete-X; nested brief total outage;
      full AR/SOF overlap; short flight; adjusted/spliced route; cached/missing
      data; midnight/DST/subminute; two-/three-page dense leg; five normal legs;
      over-budget omission; print/PDF/evidence/publication failure controls.
      Fault controls live in isolated test infrastructure, not public APIs.
- [ ] Download and inspect ZIP members/manifest/stats, PDF rows/fonts/page
      sizes/count/order, evidence mappings/hashes/diagnostics, and legacy
      equivalence. Round-trip ZIP import to prove optional members do not change
      mission/route/POI import. Preserve full actual PDF color/grayscale
      rasters.
- [ ] Run three cold five-leg requests with one browser and shared deadline;
      compare deterministic content/geometry/page rows/preview pixels/
      normalized PDF structure. Record legacy time, render stages, proxy total,
      omitted-path timing, memory, owner identities, and teardown.
- [ ] Exercise actual rendered-browser enabled/disabled/omitted journeys through
      Nginx. Download the ZIP, check persistent omission feedback,
      dismiss/reopen, and verify ordinary success. Also run concurrent export
      and client disconnect controls; prove no blocked event loop or surviving
      worker.
- [ ] Run applicable static/backend/frontend gates, focused Node/browser/tools
      controls, and exact-head CI gates. Fixes require a new committed candidate
      and affected plus final production acceptance on that candidate.
- [ ] Present new dense/continuation/five-leg actual PDFs and production
      download behavior for explicit customer acceptance and scan/readability
      feedback. Preserve acceptance scope and user source; do not inherit #312
      acceptance or invent measured scan duration.
- [ ] Tear down the recorded project, private volumes/networks, browsers,
      workers, subprocesses/listeners, temporary paths, and task image tags.
      Check host ownership where sandbox namespaces hide processes. Preserve
      evidence/open-PR worktrees, actor/shared configuration, and phase-one.
- [ ] Push feature PR(s) against `dev`; independent review, exact-head checks,
      production evidence, and customer acceptance precede merge. No merge until
      required gates pass. After merge, remove only each task's worktree/
      local/remote branches/temp resources per AGENTS.md. Keep default-off.

## Completion boundary

Delivery means accepted dense/multi-leg PDFs, complete all-row and diagnostic
evidence, legacy compatibility, real enabled/disabled/omitted downloads,
qualified lifecycle/deadline/proxy behavior, reviewed exact-head CI, and audited
cleanup. Shared production enablement and legacy PPTX replacement are separate
decisions. Report any blocked environment control or remaining owned resource
precisely; neither API-only success nor checkpoint evidence completes this
stage.
