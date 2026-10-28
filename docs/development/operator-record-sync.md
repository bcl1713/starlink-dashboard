# Operator saved-record synchronization

Operator polls saved changes every two seconds while its page is visible. The
engineering acceptance target is five seconds from a successful server save to
the other foreground client's rendered saved state on a healthy local backend.
Suspended/background browsers and larger recovery backlogs are measured
separately. They are not promised background timer delivery.

Both devices must use the same backend, mission and live/simulation context.
Drafts remain local to their originating browser tab. Incoming saved changes
preserve typed input and its original base version; a stale save still requires
explicit HTTP 409 review. Synchronization never retries writes automatically.

## Read contract

`GET /api/v2/operator/records` includes captured `source` metadata even for an
empty page: requested mission, store, epoch, source mode, simulation namespace,
replay and operating context. Workspace reads send `source_identity` and
validate the response before using its snapshot high water `H`. Their
continuation cursors additionally bind the full source context. Other readers
retain their existing snapshot cursor contract.

`GET /api/v2/operator/record-changes` accepts `mission_id`, `source_identity`,
`after_seq`, optional `cursor` and a `limit` from 1 to 200 (default 200). It
returns the latest revision of each changed record in a frozen sequence
interval, including removals, with `H`, `as_of`, `cursor` and captured `source`.
Advance the checkpoint only after all pages validate and finish. Original
snapshot pages and cursors are maintained independently from the changed-record
overlay.

Network/service failures retain last-known data and retry on the foreground
interval. Invalid checkpoints or replaced sources cancel the old read generation
and request a fresh identity-validated baseline. Quarantine remains shared with
the editor until that baseline succeeds. Previously displayed saved versions
never regress when newer snapshot pagination displaces a record.

One workspace hook owns the timer. Editor observers share its saved data without
starting another polling owner. Visibility, focus and online events request
prompt catch-up; simultaneous triggers share an in-flight read. Changed batches
refresh only that mission/context's timeline and event projections. Idle reads
add approximately 30 small GETs/minute/client; they do not reload history or
snapshot pages. Other context/health/projection queries retain their own costs.

## Reproduce acceptance

Use a clean feature worktree with dependencies installed and the
actor-configured Docker daemon available. The runner requires a new private
project and evidence directory. It archives the exact committed candidate and
builds the production backend/frontend Dockerfiles, including Nginx.

```sh
OPERATOR_SYNC_CHROMIUM=/path/to/installed/chrome \
  timeout --kill-after=15s 35m \
  python3 tools/acceptance/operator-record-sync/run.py \
  --candidate "$(git rev-parse HEAD)" \
  --project starlink-operator-record-sync-your-task \
  --evidence /tmp/operator-record-sync-your-task-evidence
```

Omit `OPERATOR_SYNC_CHROMIUM` when Playwright's expected browser is installed.
The test creates separate 1920×1080 laptop and 390×844 phone browser contexts.
It checks bidirectional scheduling, conference establishment/closure, connected
customer counts, call rescheduling/cancellation and timeline convergence. It
also exercises snapshot pagination, dirty drafts and 409, genuine browser
lifecycle suspension, offline/reconnect, an actual stopped/restarted backend,
SPA unmount/remount, a 205-record incremental batch, mission isolation and
actual live-to-simulation store/context replacement.

All records, routes, telemetry and runtime configuration are synthetic and local
to the disposable project. No production instance or aircraft hardware is
involved. Lifecycle suspension evidence is distinguished from unit tests that
simulate hidden-document events.

`operator-record-sync-proof.json` records per-operation propagation
milliseconds, idle request counts by endpoint/client, catch-up measurements and
scenario results. Desktop/mobile screenshots and Playwright traces accompany it.
`summary.json` records candidate/image identity and teardown results;
`ownership.json` records commands, PIDs/process groups, private volumes and
temporary paths. The runner tears down its services, networks, volumes, images
and relay on success or failure, and retains evidence for review.
