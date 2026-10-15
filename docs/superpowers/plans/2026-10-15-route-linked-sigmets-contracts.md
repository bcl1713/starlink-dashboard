# Route-linked SIGMET Technical Contracts

This is the technical companion to the
[implementation plan](2026-10-15-route-linked-sigmets.md), implementing the
[approved spec](../specs/2026-10-15-route-linked-sigmets-design.md). These are
planning decisions, not a claim that the feature or acceptance exists.

## Wire Types and Cross-language Identity

Python models live in `B/app/models/route_sigmets.py`; matching strict Zod
models live in `F/src/services/route-sigmets.ts`. Use existing extra-forbidden
`Contract` and safe-integer UTC millisecond conventions. SHA-256 keys are 64
lowercase hex characters. All references below use the path abbreviations in the
main plan.

| Type                | Required fields                                                                                                                                                                                                                                                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RouteContext        | `context_key`, `source: ordinary\|simulation`, `route_id`, `route_name`, nullable `runtime_id`/`run_id`, ordered `points` as lon/lat pairs; simulation requires both IDs. Internal only: snapshot points/waypoint occurrence mappings. Wire context omits points.                                                                       |
| IntersectionSpan    | Zero-based `segment_index`, `start_fraction`, `end_fraction` with `0 <= start <= end <= 1`; `entry` and `exit` as `[lon,lat]`; `boundary_error_m <= 18.52`. Equal fractions represent witnessed point contact.                                                                                                                          |
| GeometryResult      | `matches` with canonical bulletin/feature IDs and spans; `unresolved` with bounded feature IDs/reason; `complete` boolean and reason. `complete=false` prohibits a definite zero-match conclusion.                                                                                                                                      |
| BulletinGroup       | `bulletin_key`, `semantic_digest`, sorted distinct `feature_ids`, reported properties, normalized geometries, `identity_uncertain`, validity and original expiry. Internal only; no duplicated bulletin in notice wire data.                                                                                                            |
| RouteSigmetEntry    | `notice_key`, `bulletin_key`, `semantic_digest`, `feature_ids`, `spans`, `attention_order`, `acknowledged`, `valid_from_ms`, `expires_at_ms`, `identity_uncertain`.                                                                                                                                                                     |
| RouteSigmetSnapshot | `schema: route-sigmets-v1`, `generated_at_ms`, `settings_revision`, `state_revision`, `generation_id`, nullable wire `context`, `sigmet_product: WeatherProduct`, `status`, nullable `reason`, `complete`, `truncated`, `entries`, `unresolved`, `future_feature_ids`, `omitted_features`. Product carries original deadlines/coverage. |
| NoticeMutation      | Only `context_key`, `notice_key`, `semantic_digest`, `acknowledged: bool`.                                                                                                                                                                                                                                                              |
| NoticeConfirmation  | Mutation fields plus confirmed `state_revision` and `attention_order`.                                                                                                                                                                                                                                                                  |

`status` is `off|no-route|evaluating|ready|stale|incomplete|unavailable`.
`truncated` remains false: inability to return the full result yields incomplete
or unavailable, never a silently shortened successful response. Unresolved
reasons are
`unlocated|boundary-uncertain|identity-uncertain|invalid-route|limit`. Use a
500-entry advisory-group cap, 100,000 spans across the whole result, and 8 MiB
total encoded response/worker-result cap. Validate aggregate limits and unique
IDs as well as per-field types; collection source limits still apply.

The route key hashes bytes: UTF-8 `route-context-v1` plus NUL, then source,
route ID, runtime ID and run ID as unsigned big-endian 32-bit UTF-8 lengths
followed by their bytes (null IDs use empty strings), followed by big-endian
32-bit point count and big-endian float64 longitude/latitude for each point.
Canonicalize negative zero; reject nonfinite/out-of-range coordinates. Include
neither altitude, timing nor display name. Python `struct` and browser
`DataView` must produce the same pinned hashes; use the existing `@noble/hashes`
dependency.

Bulletin identity uses issuer/FIR/canonical series/original validity, with a
normalized-content hash fallback for unresolved identity. Sort geometry
variants, canonicalize ring rotation/direction and hole/component ordering
without losing hole roles, and collapse whitespace in raw text. Do not round
distinct positions into equality. Hash semantic properties listed in the spec,
excluding acquisition metadata. Cancellation/replacement uses existing verified
lineage, never series alone. A semantic change cannot inherit an old
acknowledgement.

`generation_id` hashes route context, settings revision, source instance and the
time-eligible entry/revision set. Notice state revision is separate. The browser
additionally uses local request epochs; neither hash nor server UTC timestamps
are a sortable substitute for rejecting obsolete read completions.

## Great-circle Geometry Method

Use existing Shapely for planar predicates on the normalized lon/lat rings,
including holes and existing dateline splits. Shapely does not evaluate
spherical curves; its
[coordinate-system contract](https://shapely.readthedocs.io/en/stable/manual.html#coordinate-systems)
requires the great-circle path to be handled explicitly. No longitude/latitude
straight chord or bounding-box overlap alone is a route intersection test.

Implement conservative adaptive interval subdivision of each shortest spherical
route arc. Sphere radius is 6,371,008.8 m for numerical error measurement;
terminal arc length is 18.52 m (0.01 NM). This is an error tolerance, not a
route corridor. An arc with `pi - angle <= 1e-10` radians is ambiguous and
unresolved. Skip coincident successive coordinates; a route with no nonzero arc
is unusable.

For unit endpoint vectors `u,v`, angle `a = atan2(|u×v|, u·v)`, and
`w = (v - u*cos(a))/sin(a)`, evaluate `r(s) = u*cos(s) + w*sin(s)` for
`0 <= s <= a`. This is the same shortest great-circle intent as
`globe-route.ts`; no replay clock participates. For each candidate subinterval,
calculate a conservative lon/lat enclosure:

1. Latitude extrema include endpoints and roots of
   `-u_z*sin(s) + w_z*cos(s) = 0`, using `atan2(w_z,u_z) + k*pi` inside the
   interval. Evaluate actual extrema; endpoint-only latitude boxes fail at high
   latitudes. Inflate bounds by `1e-9` degrees as a numerical guard.
2. Longitude is monotonic away from a pole: its derivative has constant sign
   `(u_x*w_y-u_y*w_x)/(x*x+y*y)`. Unwrap consistently and split each enclosure
   at ±180 before testing normalized polygons. A subinterval containing a pole
   uses all longitudes; unresolved numerical winding must not be rejected.
3. Query polygon candidates using their bounds, then actual Shapely predicates.
   If an entire enclosure is disjoint, that interval is outside. If the polygon
   covers the entire enclosure, it is inside. Otherwise subdivide, including
   exact point predicates at endpoints/midpoint as intersection witnesses.
4. At terminal length, a witnessed contained/touching point proves a match, with
   boundary locations bracketed to <=18.52 m. A terminal bracket between a
   certified interior and exterior proves a crossing by continuity; retain its
   boundary error instead of inventing an exact boundary coordinate. A
   boundary-adjacent interval with no witness stays unresolved, including
   tangencies the numeric method cannot prove. Never promote approximate chord
   contact to a confirmed match or discard an unresolved sliver as outside.
5. Merge only contiguous witnessed/inside intervals for the same
   feature/segment. Carry boundary uncertainty separately; never bridge a hole
   or unresolved interior interval. Separate proven spans survive as matches
   even when other spans are unresolved. A fully disjoint result requires every
   interval to be certified outside. Cap subdivision at 1,000,000 interval
   visits and depth 52; reaching either limit marks incomplete and stops rather
   than clipping output.

Independent fixtures: equator/meridian polygons have analytically known route
fractions; construct high-latitude and seam fixtures from an independently
calculated great-circle plane/latitude-extremum formula. Include a narrow
polygon centered away from source vertices, a route in a hole, point contact and
multiple holes. Check reference positions by spherical distance, not production
helper output. A sub-tolerance sliver or unstable tangent must be unresolved or
witnessed, never a certified nonintersection. Rendering interpolates reported
fractions on the original arc and must respect separate spans/unknown gaps.

## Persistence, Lock Order and Worker Ownership

State JSON contains `schema: route-sigmet-state-v1`, `state_revision`,
`attention_counter`, context LRU records and keyed notice records with expiry,
acknowledgement and attention order. First registration and Show again consume
an ordinal; identical Clear/Show again retries are no-ops. A false write on an
already pending notice does not repeatedly promote it. Reconcile persists only
changed state. Expiry pruning does not depend on the feed returning a record.
Never mutate legacy aviation preferences when creating this sibling file.

Lock sequence: copy route under active-leg lock, release before geometry, then
join results under notice lock. For acknowledgement, execute the complete
bounded critical section in `asyncio.to_thread`: active-leg lock first, notice
file lock second; verify current immutable route/feed identities and actual UTC
eligibility inside the notice lock immediately before writing. Release in
reverse order; never acquire active-leg/GFS/settings locks inside a notice lock.
Do no source/worker awaits there. Revalidate before response; supersession
returns 409, and any already-written old-key record cannot affect a replacement
because acknowledgement keys include exact context and semantic revision.

One shared geometry task per app owner and one latest pending input are allowed.
Same-input readers join it with reference-counted leases. Last-reader departure,
supersession or shutdown cancels it; repeated cancellation must await cleanup.
Use bounded stdin and chunked stdout, reject >8 MiB before parsing, and discard
stderr. Set one-CPU affinity where available, 512 MiB address-space limit and
five-second CPU limit; parent enforces five-second wall time, TERM then
one-second grace, then KILL only its verified child/session and reap. All
descriptors close in `finally`. Invalid or timed-out output becomes unavailable.
Keep old/candidate results to at most two bounded cache entries; requests
revalidate their input identity before admission. No work at startup, all-off or
zero readers.

## Browser Source and Drawing Ownership

`RouteSigmetSource` is keyed by QueryClient in a WeakMap. Its view contains
`snapshot: RouteSigmetSnapshot | null`, exact
`collection: AviationCollection | null`, `available`, `error`, and a
data-reservation lease. It owns the route query, immutable SIGMET report fetch
and lifetime until the last subscriber leaves. A shared query client must never
create two source/payload loops.

Fetch GET `/api/aviation-weather/v1/route-sigmets` at five seconds only while
SIGMETs are enabled, visible and online, with React Query `networkMode: always`
and visibility-driven enablement rather than focus gating. Abort older request
epochs, set retry false, bound each request to ten seconds, and catch up on
resume. A returned product instance triggers its immutable payload fetch in the
same cycle using existing bounded/hash-verified report admission. Configuration
alone drives demand and report access; neither screen waits for the old catalog
timer. All response bytes and decoded strings count against WeatherBudget.

Use one budget slot for each active transfer, not while awaiting another slot.
Reserve decoded results before parsing, release raw buffers after admission, and
reserve existing plus candidate data during replacement. Do not store a second
unaccounted copy in query caches. Query cancellation/GC releases leases. Failed
payload binding gives a loading/unavailable view, never mismatched data. Keep
original deadlines using a server-UTC/monotonic anchor and one next-boundary
timer; browser local time changes cannot extend validity.

The source owns data only. `SigmetPresentationInput` contains the source view,
`localContextKey: string | null`, confirmed filter boolean and anchored `nowMs`.
`SigmetPresentation` exposes `view: AviationLayerView`, visible `notices`,
`highlightUnavailable: boolean` and `dispose(): void`.
`createSigmetPresentation` consumes its leased data plus the current local route
key and confirmed filter; it owns base/highlight drawings and GPU reservations.
`AviationController` external mode merely attaches that borrowed SIGMET view; it
never disposes externally owned drawings. The presentation owner releases before
its data lease, and on hide/offline, disable, incompatible generation, expiry or
unmount. Same-geometry source refresh may reuse owned buffers only when
eligibility/filter identities remain compatible.

Highlight exactly the three visible pending notices, in persistent attention
order. Duplicate split parts share one notice label; far-side features remain
depth-tested. Unknown highlight geometry leaves text with an explicit
limitation. No unknown-location feature is assigned an invented span or silently
filtered out of Configuration. Local SIGMET picking and general Overview chooser
entries are removed; unrelated station inspection retains its existing behavior.

## Assertion Anchors for Task Tests

Use these named cases in each task's test area, with its described fixture
setup:

```python
# Task 1: test_legacy_filter_defaults_false
assert AviationSettings().sigmet_intersecting_only is False
# Task 2: test_equatorial_crossing_has_analytic_spans
assert abs(span.start_fraction - 0.25) * arc_length_m <= 18.52
assert abs(span.end_fraction - 0.75) * arc_length_m <= 18.52
# Task 3: test_repeated_clear_is_idempotent
assert repeated.state_revision == first.state_revision
assert reopened.records[notice_key].acknowledged is True
# Task 4: test_old_revision_clear_returns_conflict
assert response.status_code == 409
assert replacement.acknowledged is False
# Task 8: test_propagation_and_cleanup_evidence_required
assert report["elapsed_save_to_display_ms"] <= 8000
assert report["cleanup"]["ports_free"] is True
```

```ts
// Task 5: two_consumers_share_source_and_ignore_obsolete_read
expect(sourceFetch).toHaveBeenCalledTimes(1);
expect(current.entries[0].acknowledged).toBe(true);
// Task 6: failed_clear_keeps_notice_pending
expect(clearButton).toBeEnabled();
expect(notice.acknowledged).toBe(false);
// Task 7: three_cards_and_overflow_without_dashboard_actions
expect(cards).toHaveLength(3);
expect(overflowCount).toBe(1);
expect(overviewSigmetActions).toHaveLength(0);
```

## Acceptance Runner and Final Commands

Extend the existing aviation runner rather than add a second stack. Parameterize
its project and ports, replacing hard-coded values in base URL, binding checks
and cleanup. Default to a unique `starlink-route-sigmets-<task-suffix>` project;
reserve loopback ports before start and refuse existing labeled resources.
Record PID/process group, command/session handle, source temp directory, private
volumes, ports, context/socket and full candidate SHA before resource creation.
Use `try/finally` in Playwright for every extra context/page/probe, preserve
proxy/CA settings, and never replace the actor's Docker configuration.

Archive the exact committed candidate for both images and browser test sources;
reuse provisioned dependencies only after matching the candidate package lock.
Transport fixtures may control failure/feed content and real UTC independently
of replay time, but do not intercept the route-SIGMET API or browser mutations.
Update old production SIGMET click-inspection expectations to passive cards and
Configuration report review; retain cancellation, hole, seam, source and station
regressions. Put final PASS evidence after verified cleanup, not before it.

Run from `B` (focused task checks precede these full relevant regressions):

```sh
timeout --kill-after=10s 10m uv run --with-requirements requirements-dev.txt --with-requirements requirements-gfs.txt pytest tests/unit/test_route_sigmets_*.py tests/unit/test_aviation_weather_*.py tests/unit/test_main_aviation_weather.py tests/unit/test_gfs_settings.py tests/unit/test_gfs_api.py -q
```

For task red/green, replace the pytest selection with its named area files; Task
1 selects `test_route_sigmets_contracts.py` and `test_route_sigmets_context.py`.
From `F`, focused checks use:

```sh
timeout --kill-after=10s 10m npm run test:unit -- src/services/route-sigmets.test.ts
```

Select the task's colocated test paths. Require FAIL before code and PASS after;
run the existing regressions named in that task alongside the new tests.

Run from `F`, after installing candidate-locked dependencies with bounded
`npm ci`:

```sh
timeout --kill-after=10s 10m npm run test:unit
timeout --kill-after=10s 10m npm run build
timeout --kill-after=10s 10m npm run lint
```

Run changed Python Black/Ruff and Markdown/Prettier/filename checks using the
repository's pinned settings; restrict formatting fixes to changed files. Run
`tools/tests/test_route_sigmets_acceptance.py` with pytest from the root under a
ten-minute wall limit. Commit before production acceptance, then from root:

```sh
timeout --kill-after=10s 40m tools/acceptance/aviation-weather/run.sh "$(git rev-parse HEAD)" "$AVIATION_ACCEPTANCE_BROWSER"
```

The browser path is the existing provisioned executable; the runner must fail
preflight if missing. Synthetic captures are deterministic behavior controls.
Separately replay a pinned, hashed real SIGMET capture through normalization and
the same native renderer, preserving source UTC and labeling dated evidence. If
unavailable, record that gate unverified; synthetic data cannot replace it. No
target-workstation GFS performance or NOAA source validation is claimed.

After every check, including timeout: stop/reap recorded processes, close
browser children, tear down only the recorded Compose project and its disposable
volumes, and verify scoped container/network/volume listings and listeners are
empty. Use an approved host check when sandbox PID visibility is insufficient.
Preserve logs/screenshots/API assertions/provenance under `test-results`, and
report exact remaining resources if teardown cannot be verified. No service
stays running for PR review. After all gates and whole-branch review, push the
implementation PR against `dev`; merge only through the repository's reviewed
checks.
