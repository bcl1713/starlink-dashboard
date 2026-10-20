# Operator evaluation on the normal nonproduction dashboard

Use the existing installation, mission planner and simulation. Calls,
conferences and display controls have preliminary usability approval only. The
steps below evaluate the remaining work; they are not merge approval. No
training launcher or additional weather, ADS-B, satellite or network service is
required. Optional sources may truthfully show unavailable.

## Update the existing installation

Run in the **existing nonproduction deployment checkout**, using its usual
Compose files and project name throughout. Keep its `.env`, settings, route
volumes, mission directories and Operator volume. Do not use the aircraft
production installation. If you use custom Compose files, use the same `-f` and
`-p` options for every command below.

1. Confirm a clean checkout of `dev` before updating. Preserve any local changes
   before continuing. Fetch and advance the reviewed development branch.

   ```sh
   git status --short --branch
   git fetch origin dev
   git merge --ff-only origin/dev
   git rev-parse HEAD
   ```

2. Operator is enabled by default. Remove an old `OPERATOR_ENABLED=false`
   override or set it to `true` in the existing `.env`. Keep the existing mode
   configuration; use the installation's normal simulation control for the
   fictional mission. Leave `OPERATOR_EVALUATION_SESSION` unset for the durable
   `default` evaluation, or keep its existing name. It is passed through the
   backend's existing `env_file`; no Compose override is needed.

3. Build the two changed application services, then stop the backend briefly and
   back up the entire Operator volume before replacement. The following uses the
   repository's standard service names. Retain the backup privately; it includes
   all live, simulation and historical journals.

   ```sh
   docker compose build starlink-location mission-planner
   mkdir -p backups
   docker compose stop starlink-location
   docker compose run --rm --no-deps -T --entrypoint tar starlink-location \
     -C /app/data -czf - operator > "backups/operator-before-pr383-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
   docker compose up -d --no-deps starlink-location mission-planner
   docker compose ps starlink-location mission-planner
   ```

   Check that the backup command succeeded before continuing. Do not remove
   volumes or change the Compose project. Restart the old backend if the backup
   fails. Existing weather/telemetry services do not need rebuilding.

4. Reload the browser. Choose **Operator** in normal navigation (the workspace
   entry is `/operator`). If setup is required, use **Initialize simulation
   journal** once for the displayed evaluation. Initialization does not reset or
   adopt any previous journal. A corrupt/recovery-required store requires its
   existing recovery procedure, not reinitialization.

## Storage and replay behavior

Mission IDs select independent logical journals, as in live storage. Simulation
uses a separate SQLite namespace under
`OPERATOR_ROOT/simulation-missions/default/`; that database holds the
mission-filtered journals for this evaluation. Changing mission, leg, replay or
restarting the backend does not replace this namespace. Live paths, identity,
versioning, receipts and recovery are unchanged.

Each paced simulation report carries its actual `provenance.replay_run_id`.
Ordinary Activate has no replay ID: new reports instead carry an additive
`provenance.operating_context_id` derived from the existing runtime identity,
activation revision and active route. Reactivation or backend restart retires
readiness evidence without changing journals. Reloading a page does not. The
health `simulation_run_id` identifies the durable evaluation namespace;
`replay_run_id` identifies the current flight replay. These are deliberately
separate. Corrections preserve the report's original replay. Explicitly starting
an unstarted carried call creates a new revision attributed to the current
replay; it does not rewrite earlier revisions.

Unfulfilled call requirements and unresolved issues remain actionable mission
obligations. Old connections, started/completed calls, conference verification,
transport checks and capability assessments do not establish readiness in a new
replay. Find those reports in **History**, with their original associations and
revision history. Conference **definitions** remain visible and selectable for
calls throughout the mission, including accepted records created before this
fix. Use **Reestablish** on the same definition to explicitly report a new
session, then verify it and report customer joins independently. No clone or
migration is required. A new immutable revision records the new context; earlier
revisions retain their original provenance. Corrections alone never refresh
readiness. Missing replay/source data does not prove readiness.

Automatic context uses the existing active mission/route resolver, flight phase
and simulation run. Preflight/ground-gap/postflight defaults follow the ordered
itinerary. A deliberate mission selection is browsing only. **Return to active
mission** resumes automatic following. New drafts capture their context once;
leg changes do not move them. Across replay changes, retained drafts/submissions
remain pinned. Resolve uncertain receipts with Exact retry; an unaccepted
old-run command cannot create a new-run report. Use Copy input to current replay
to deliberately continue an unsent draft while retaining its original. Mission
and leg associations are preserved in both copies.

### Previously created per-run journals

`OPERATOR_ROOT/simulation/<old-run-id>/` stays separate and intact. No automatic
migration, merge, adoption or deletion occurs. New mission journals start empty;
ordinary History and the new mission ZIP do **not** silently include those old
stores. Keep old archives. For a particular old store, the existing maintenance
CLI can check/back up it, and the export command can produce a separate
historical journal ZIP without changing its associations:

```sh
docker compose exec -T starlink-location python -m app.operator export \
  --root /app/data/operator --mode simulation --run OLD_RUN_ID \
  --mission MISSION_ID --output /tmp/old-run-journal.zip
docker compose cp starlink-location:/tmp/old-run-journal.zip ./old-run-journal.zip
docker compose exec -T starlink-location rm /tmp/old-run-journal.zip
```

Substitute actual IDs and a unique output name; export refuses to overwrite an
existing destination. This is a journal-only archive, not the customer briefing
ZIP and not an import/migration mechanism. Add `--mission-journal --run default`
for maintenance/export of the new evaluation namespace.

### Deliberately start a fresh evaluation

Keep `default` for normal repeat runs. To start fresh, set a new simple name,
for example `OPERATOR_EVALUATION_SESSION=evaluation-02`, in the existing `.env`,
then run `docker compose up -d --no-deps --force-recreate starlink-location`.
Initialize the displayed new journal from Operator. This selects a new
installation-wide simulation evaluation namespace containing separate logical
journals per mission; it does not modify any earlier evaluation. To revisit one,
restore its previous setting (unset means `default`) and recreate the backend.
Do not delete files or use restore to start fresh. Live storage ignores this
setting. No session service or training environment is involved.

## Short human acceptance sequence

Use one explicitly disposable fictional mission with two timed legs and a
reasonable ground stop. Use **Activate** for routine work with real elapsed time
and normal simulation telemetry. Use **Simulate leg** only for paced flight/time
progression; its network panels are Unavailable when no valid metric source
exists. Note the mission ID, evaluation name and deployed commit. For each step,
record the first confusing control, unnecessary selection or unclear outcome—not
merely API success. Stop on a confusing action and report the screen/action and
expected result. Existing source-specific tests stand; absent optional telemetry
is not a reason to manufacture providers.

1. **Enter and orient.** Use **Activate** for leg one through Missions, then
   open Operator through navigation. Confirm its mission/leg names and phase
   without selecting them. Create a note and check its suggested association.
   Park an unsaved draft. Reload: automatic context and the draft should remain
   available. Browse another mission, confirm aircraft activation stays
   unchanged, then use Return to active mission.
2. **Move a transport.** In Transport, record intention and request, then the
   actual applied transport and verification independently. Try an applied-only
   change during a reported customer connection. Inspect the review's timing,
   unknowns and reported-versus-modeled basis. Correct one stage and inspect its
   earlier version. Judge whether the next action is obvious and quick.
3. **Work an issue.** Create an issue, set mitigation, monitor it, schedule a
   follow-up, add an update, resolve and deliberately reopen it. Correct an old
   message without replaying Resolve/Reopen. Record functional capability and
   redundancy independently; neither should silently determine the other.
4. **Keep the journal.** Add a note, correct it, inspect history, and exercise
   remove/restore on a disposable entry. Verify named mission/leg/ground-gap
   associations and original text. Use History's loaded-page search and load
   more when needed; it must not imply a complete search of unread pages.
5. **Watch the next requirement.** Schedule a near-future call and issue
   follow-up. Find the Next requirement, preparation and overdue indications
   while ordinary model advisories are present if available. Check Local alerts
   and acknowledgment discoverability. Missing ETA/model data must remain
   explicit while journal work remains usable.
6. **Ground stop, leg two, replay.** At leg-one arrival create a ground-gap
   note. Start leg two: new drafts follow its context, the parked draft keeps
   its old context, and earlier records remain in History. Restart the backend
   and replay the same mission. The journal remains; yesterday's connections,
   checks and verified bridges must not count as current. Unfinished
   requirements remain requirements. A different mission must show only its own
   journal.
7. **Export and transfer.** In Mission records, use the existing Export control
   to obtain the original single mission ZIP, including the customer PDF. Open
   the PDF and inspect `operations/journal.json`, audit/history and named leg
   associations in the ZIP. Expect all replay histories in this evaluation, with
   original replay provenance. Keep the complete ZIP privately; share only the
   extracted customer PDF when appropriate. Test ordinary planning-only import
   in a clean destination or explicitly isolated namespace, with a new mission
   ID. Confirm no Operator records are restored and unrelated destination
   missions/journals are unchanged. Do not overwrite ordinary stored missions.

## Focused regression check before resuming evaluation

- With ordinary **Activate**, confirm mission/leg/phase, create CABLES, and
  select it in a scheduled call. Existing accepted definitions must also be
  selectable.
- Establish and verify it; associate a second call without recreating the
  bridge.
- Deactivate and activate another leg, or start **Simulate leg**. The definition
  remains; old establishment, verification and customer connections are marked
  historical. Explicitly reestablish and verify the same definition. Inspect its
  earlier revisions in History.
- Check ordinary Overview values marked **SIMULATED DATA**. Start a paced
  replay: selected network panels show **Unavailable**. Deactivate and
  **Activate** again: ordinary values return. Exercise a preset and one
  visibility toggle.
- Keep a draft and a pending save across the transition: their original context
  stays pinned, and exact retry resolves the original request without
  duplication.

No existing per-run journal is migrated or combined by this regression fix.

## Cockpit cards and save diagnostics

**Now** and **Communications** show **Active Calls** and **Active Bridges**
first. Use the existing call actions on each card. A finished call leaves its
bridge session open: explicitly close the bridge from its card. Closed
definitions stay reusable in Communications. Each customer interval remains an
independent report. Earlier replay evidence does not create an active session.
The sections cover loaded records; use Load more records when the
incomplete-page notice appears.

A submitted save immediately shows **saving**. Its receipt confirms acceptance;
a separate authoritative current-row read makes the saved card visible without
waiting for list, history or model-event refreshes. This is confirmed server
data, not an optimistic save. Exact retry still uses the original request and
receipt. Snapshot cursors/watermarks and historical provenance are unchanged.
Record commands reread the latest version before acting, including during a
background refresh. An unreadable current row still shows **accepted, current
state unavailable**, never a fabricated current state.

Focused local measurements for this follow-up (not a deployment latency
promise):

| Measurement                                                                            |  Before |   After |
| -------------------------------------------------------------------------------------- | ------: | ------: |
| Local conference SQLite/API save, median of five                                       | 4.35 ms | 4.20 ms |
| Same API save plus authoritative current GET                                           | 6.67 ms | 6.46 ms |
| Controlled frontend receipt (50 ms POST)                                               |   52 ms |   52 ms |
| Controlled frontend current row returned (50 ms GET, 200 ms list/history refresh each) |  504 ms |  104 ms |

The controlled test uses delayed API responses to isolate frontend ordering; it
is not a measurement of Docker or your network. It also verifies pending
feedback, a visible accepted bridge while list reads are unresolved, and no
second POST. The local API fixture did not reproduce the reported 5–6 second
HTTP acknowledgment. No SQLite durability settings or journal storage were
changed to chase that unverified cause.

If acknowledgment is still slow after this update, inspect the save request in
browser Network tools. `Server-Timing` separates `operator_request` (full server
route), `operator_gate` (initial admission, including binding wait),
`operator_binding` (mutation admission), and `operator_command` (validation,
atomic journal write/commit and receipt). A slow HTTP request with a short
`operator_request` points outside this handler; a long admission phase can
identify contention with other Operator reads. These values contain no journal
text. They do not separate storage fsync from each individual validation step.

Browser Performance measures `operator.save.queue`, `.http`, `.current`,
`.refresh`, `.visible` and, for actions requiring a captured clock, `.clock`
record the corresponding stages. Queue covers command-owner dispatch, current
covers the authoritative reread, refresh covers background query refreshes, and
visible covers the confirmed-row-to-render interval. In browser DevTools
Console:

Inspect `performance.getEntriesByType("measure")` for these saved stages.

## Arrival after ordinary Activate

A fresh, moving position and valid destination route projection support an ETA.
The reported one-way route projected its destination to `100.00000000000003`
through floating-point rounding, making it ineligible. The actual response
confirmed `upcoming: false` and null ETA values. Computed route projection is
now bounded to the valid endpoint; invalid externally supplied projections
remain rejected. No time offset or flight progression is added. Activate the leg
normally after updating to rebuild its generated POI projections.

Predeparture shows the scheduled departure. In flight, missing route progress
now says **Route position unavailable — ETA unavailable**, while a missing or
invalid destination projection says **Destination route position unavailable**.
Position freshness and passed-destination explanations remain separate. Paced
Simulate leg continues using its existing route and mission clock. If the
one-way symptom persists, retain `/api/overview/upcoming-pois` fields `state`,
`flight_phase`, `current_route_progress`, `position_state`, and the arrival POI;
those identify the remaining source condition without sharing the entire route.

### A 409 with `event_snapshot_changed`

This code on the event GET means inputs changed while a consistent operational
snapshot was being assembled. It is distinct from a journal write/version
conflict. A successful call or conference receipt remains accepted even if its
subsequent background event refresh conflicts.

Post-save invalidations now share an in-flight event refresh instead of
canceling it and starting duplicate backend work. A timing guard validates
planning and telemetry against one coherent input capture instead of capturing
the full input set twice. A read-only event refresh retries this specific
retryable conflict once after 100 ms, starting a new complete snapshot. It never
retries an acknowledgment or a journal mutation. Persistent conflicts keep the
previous snapshot with the existing unavailable/current-state-unknown notice;
source, version and acknowledgment guards remain enforced. An individual 409 can
still appear in DevTools when the bounded GET retry subsequently succeeds.
