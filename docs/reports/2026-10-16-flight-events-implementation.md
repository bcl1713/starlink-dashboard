# Flight events and telemetry implementation

Native implementation is pushed in a draft pull request. No deployment or merge
has been performed. The initial browser-blocker diagnosis was incorrect: the
actor-owned Playwright cache contains Chromium and the configured rootless
Docker daemon is healthy. Local production-container and headed CDP browser
checks have now passed using that existing runtime. The placeholder default
platform descriptor was not used or modified.

## Behavior

The live event ledger separates departure taxi, takeoff, inferred landing,
arrival taxi and parking. Capture begins 30 minutes before actual off-blocks and
ends 30 minutes after the first confirmed destination park, including DV
offload. Repositioning does not reopen automatic arrival. Operational fuel stops
can remain within a single planned leg. Missing evidence and moving startup
require uncertainty/manual correction, rather than invented event times.

Raw Prometheus extraction has independent, leased interval jobs. Incomplete
queries retry with bounded backoff and eventually seal all available data with
explicit gaps. Corrections reuse prior sealed observations after rolling history
expires. CSVs, manifests and mission ZIPs distinguish missing values, unknown
source freshness, measured zero, raw series labels and revision identity.

## Verification and review

Independent whole-branch review identified three important archive defects:
sealed-history reuse, independent raw coverage, and exhausted query recovery.
Each was reproduced by a failing regression before correction; those regressions
and their surrounding integration checks passed afterward. No critical or minor
findings were reported by that review. The final canonical checks are recorded
below.

The provisioned-browser journey checks Overview taxi, inferred landing, parking
and uncertain states at 1920 by 1080, with exact candidate revision metadata. It
passed on the existing cached Chromium browser through a local CDP session.
Synthetic tests do not establish field calibration of the configured movement
thresholds.

## Decisions made during execution

- Cloned the absent repository and used an isolated feature worktree based on
  dev. The primary checkout has no feature edits; the cost is an additional
  checkout to retain for review.
- Ignored the worktree directory locally rather than changing the primary
  checkout's ignore file. This setting applies only to this clone.
- Completed the arrival regression with the detector integration rather than the
  initial evidence-contract commit. This changed sequencing only.
- Used SQLite sample staging and immutable snapshots, followed by automatic
  durable CSV ZIP publication, instead of individual CSV staging chunks. This
  simplifies atomic recovery at the cost of larger database and export-memory
  requirements that need operational monitoring.
- Committed coupled runtime and capture imports together to avoid broken
  intermediate imports. This produces a larger implementation review unit.
- Added movement details to Overview and the mission-scoped events API while
  preserving the old unscoped flight-status endpoint. Legacy callers must
  migrate to obtain the new details.
- Replaced the old test expectation that endpoint dwell alone lands an unbound
  route. Route-only users need a bound mission and supported evidence or manual
  events; historical endpoint-only automatic arrival is deliberately suppressed.

No reviewer-reported minor findings were deferred. The six-task plan was split
into companion files to satisfy the repository's Markdown length limit.

## Verified checks

- Final frontend tier: 1,654 unit tests passed and production build passed.
- Canonical static tier: Python formatting/lint, frontend formatting/lint,
  Markdown formatting, documentation links and typing-policy tests passed.
- Review-fix focused backend suite: 52 tests passed.
- Full backend tier: 3,442 tests passed, 20 skipped; one existing Cartopy
  rendering warning. Four additional go-around, overflight, delayed-observation
  and position-jump checks passed after that full run.
- Local headed CDP browser checks: Overview state journey passed; real operator
  event creation, parking classification and partial telemetry download passed.

## Publication and local browser evidence

The user explicitly approved pushing the branch. The branch and draft pull
request are published. The earlier automatic approval rejection no longer blocks
publication.

Both production images were built from candidate
`4bd49cf06b7130a5dcdf752cc51e3140cdfdc940`. The isolated stack used the real
backend, Nginx proxy and Prometheus with private disposable volumes. Cached
Chrome 153 ran headed through Xvfb at 1920 by 1080 and was driven over CDP. No
browser was installed, no shared application environment was changed, and no
replacement platform authority was fabricated.

The Overview journey used labeled API fixtures for taxi out, inferred landed,
taxi in, parked and uncertain states. The operator journey used the real
Nginx/backend API to create events, confirm destination parking, and download
and validate a clearly labeled partial telemetry ZIP. Aircraft telemetry was not
available in this isolated test, so the archive correctly retained gaps. There
were no uncaught page errors in the real operator journey.

All owned containers, networks and volumes were removed. Chrome, Xvfb and test
processes exited. See the
[runtime result](evidence/2026-10-16-flight-events-runtime/runtime-result.json),
[browser identity](evidence/2026-10-16-flight-events-runtime/browser-identity.json),
[operator result](evidence/2026-10-16-flight-events-runtime/operator-result.json),
[operator screenshot](evidence/2026-10-16-flight-events-runtime/operator-parked.png)
and
[Overview parked screenshot](evidence/2026-10-16-flight-events-runtime/overview-parked.png).

The repeatable operator driver is
`tools/acceptance/journeys/mission-flight-events.mjs`. Supply the isolated
`FLIGHT_EVENTS_BASE_URL`, `FLIGHT_EVENTS_ARTIFACTS_DIR`, existing
`ACCEPTANCE_CDP_URL`, and tested `ACCEPTANCE_CANDIDATE_SHA`.
