# Simulation Speed Plan: Acceptance Task

Read the [main plan](2026-10-05-mission-leg-simulation-speed.md) and approved
[acceptance contract](../specs/2026-10-05-mission-leg-simulation-speed-acceptance.md).
Tasks 1–5 must pass and be committed/reviewed before final product acceptance.

## Task 6: Production-path proof and documentation

**Files:** Create:

- `docs/missions/acceptance-assets/paced-simulation-route.kml`: timed 20-minute
  route with two distinct segment speeds and a dateline-safe representative
  path.
- `frontend/mission-planner/tests/e2e/support/simulation-run-mission.ts`:
  real-API seeding of the KML, adjusted departure, canonical X/Ka/Ku/AAR events,
  and expected event counts/transport/arrival results. No product API
  interception.
- `frontend/mission-planner/tests/e2e/simulation-run-production.spec.ts`: real
  120-second/fixed-rate runs, two windows, lifecycle, and rendered evidence.
- `frontend/mission-planner/playwright.simulation-acceptance.config.ts`:
  loopback origin validation, Chromium, one worker, zero retries, 240-second
  case timeout, 1920×1080 recording, no Vite server, and retained failure
  traces.
- `frontend/mission-planner/src/test/simulation-acceptance-config.test.ts`:
  invalid origin/credentials/config and real acceptance test selection.
- `tools/acceptance/simulation-speed/compose.yml` and `run.sh`: isolated
  archived candidate, production Dockerfiles/Nginx/Prometheus and cleanup
  ownership.
- `tools/acceptance/simulation-speed/backend_fixture.py`: live-case launcher
  that disconnects hardware connection/telemetry and public-IP/geolocation
  discovery before loading the real app; no network dialing, fake pacing, or new
  API.
- `tools/tests/test_simulation_speed_acceptance_runner.py`: source/ownership
  guards.
- `docs/api/endpoints/simulation-run.md`: new endpoints and errors.
- `docs/reports/2026-10-05-mission-leg-simulation-speed.md`: actual measured
  evidence.

Modify `frontend/mission-planner/playwright.config.ts` to exclude the production
suite from the default Vite lane. Update
`docs/setup/configuration/simulation-mode.md`,
`docs/missions/mission-planning-guide.md`, `docs/features/overview.md`,
`docs/api/endpoints/README.md`, and `docs/api/README.md` to link the new
behavior.

**Interfaces:**

- `seedSimulationRunMission(request: APIRequestContext)` returns mission/leg
  IDs, effective route, expected event count/state, and arrival coordinate.
  Build its expected schedule from fixture definitions, not product responses
  under test.
- Runner command: `tools/acceptance/simulation-speed/run.sh [--check]`.
- Inputs: full `ACCEPTANCE_CANDIDATE_SHA` derived from clean checked-out HEAD,
  `SIMULATION_SPEED_SOURCE_ROOT` owned archive directory,
  `SIMULATION_SPEED_EVIDENCE_DIR` output directory; these are task variables.
- Compose project `starlink-262`; only frontend loopback port `15262` is
  published. Backend/Prometheus remain internal, single backend worker, isolated
  named volumes.
- Browser origin: `SIMULATION_ACCEPTANCE_BASE_URL=http://127.0.0.1:15262`.
  Invoke
  `npx playwright test --config playwright.simulation-acceptance.config.ts`.
- `SIMULATION_ACCEPTANCE_MODE=simulation|live` selects the task-owned Compose
  mode. Use the normal `main:app` entrypoint for simulation and the disconnected
  fixture launcher only for live rejection controls. Record that substitution
  explicitly.

- [ ] **Step 1: Write failing acceptance contracts and journeys.** Add runner
      tests `test_rejects_dirty_or_wrong_candidate`,
      `test_refuses_existing_project`, `test_uses_archived_production_sources`,
      and `test_cleans_only_owned_resources`. Assert refusal before build/start,
      exact SHA propagation, preserved daemon/env, no force takeover, and
      failure-preserving EXIT cleanup. Config tests reject nonloopback origins,
      credentials, paths/query/hash, retries and hidden Vite server.

Browser case `120-second leg reaches all events and final arrival` starts
through the dialog in Missions while another visible window displays Overview.
Assert initial confirmed rate 10× and running panels/clock, record monotonic
start from successful activation, poll actual backend state through Nginx, and
verify final count, transport/handoff state, 100%, exact endpoint, and
POST_ARRIVAL. Expect elapsed runtime in [120, 121] seconds and report actual
late publication rather than rounding it into a pass. Record rendered video and
running/restored screenshots.

Case `fixed rate matches target runtime` replays the same fixture at 10× with
the same assertions. Case `high-rate delayed frames preserve transitions` uses a
longer fixture at 1000× and verifies final count/state; deterministic Task 2
tests separately prove event identity/order. A 0.1× bounded observation checks
slow pacing without waiting for the entire slow flight.

Case `two visible windows synchronize without focus` requires running/terminal
panel changes within three seconds of their successful backend state change,
tests independent browser contexts, and asserts no Canvas replacement or camera
intent/follow changes. Check desktop, responsive and native fullscreen captures.
Case `cancel and switch are truthful` verifies restored panels, terminal
results, and cancellation. Runner then restarts its backend and runs a separate
`restart-idle` case that reads the recorded old runtime ID and asserts new
incarnation/idle, cleared active flags, and no automatic replay. Case
`live mode rejects paced requests` uses an isolated live configuration with
controlled disconnected hardware; requests return 409 and ordinary live state
remains untouched. No dish/provider contact is required.

- [ ] **Step 2: Run red.** From root,

  ```python
  python3 -m pytest tools/tests/test_simulation_speed_acceptance_runner.py -q
  ```

  from frontend,
  `npm run test:unit -- src/test/simulation-acceptance-config.test.ts`. Record
  initial contract failure.

- [ ] **Step 3: Implement only the acceptance harness.** Add the runner
      following the existing `overview-window-sync/run.sh` ownership pattern.
      Use production images from `git archive`; configure simulation and fixed
      ground entry coordinates, ADS-B disabled, and no live inputs. Never
      intercept paced API/time in the production browser lane. Commit a clean
      acceptance candidate before running its images; record checks tied to that
      exact SHA. Schedule ordinary runs, actual backend restart and the
      restart-idle browser case, then a live-mode recreation with hardware-only
      fixture injection. Set success/failure-preserving cleanup on every path;
      never ask the browser to control Docker or add a product restart endpoint.
- [ ] **Step 4: Run green and acceptance.** Run the harness contracts and
      `./tools/verify backend`, `./tools/verify frontend`, and the canonical
      static gate with `ACCEPTANCE_POLICY_BASE_SHA` set to the verified merge
      base with `origin/dev`. Reconcile the canonical CI runtime if local Python
      differs; require all applicable exact-head CI gates. Read cloud
      Docker/proxy guidance, verify the actor's existing daemon/context, check
      resource/port ownership, and invoke the acceptance runner.

Capture exact SHA/image IDs/labels, Node/Python/browser/OS/CPU/GPU, fixture
mode, viewport/fullscreen, API responses, durations, event count/state,
cross-window timings, no-source-age regressions, restart, and cleanup. Inspect
the videos and screenshots; test assertions alone do not certify rendered
quality. Run existing globe/camera/route/history/arrival/link browser
regressions through their appropriate controlled lanes. API-mocked browser
regressions are diagnostic evidence and remain distinct from real Nginx
acceptance. Do not present the unrelated V2 platform final lane as
simulation-speed acceptance.

- [ ] **Step 5: Write measured docs/report.** Document both modes/formulas,
      exact limits, immediate planned-departure start, missing
      timing/invalid/live errors, simulated versus real time, hidden/restored
      cards, final active leg, cancellation, restart and deadline limitations.
      Record failures and pending evidence honestly. Include cleanup logs
      proving `starlink-262` containers/volumes and port listeners are gone
      while shared projects/configuration remain.
- [ ] **Step 6: Commit**
      `docs: document paced simulation behavior and acceptance`.
- [ ] **Step 7: Verify the final candidate.** Rerun affected doc/static gates,
      exact-final-head CI and production acceptance after the report commit, so
      evidence does not certify an older head. Store this run's evidence outside
      tracked files and link it in the PR without an endless report/SHA commit
      cycle.
- [ ] **Step 8: Obtain whole-branch review.** Update PR #270 around implemented
      behavior and validation, retaining #262 open until implementation is
      accepted/merged. Require independent final review, resolve findings, and
      rerun checks affected by fixes. Keep the worktree for the open PR.
      Merge/deploy are separate actions; after an authorized merge, remove only
      the task worktree/branches/acceptance/temp files under AGENTS.md.
