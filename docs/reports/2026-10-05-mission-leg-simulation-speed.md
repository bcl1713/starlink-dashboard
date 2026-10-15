# Mission-leg simulation speed acceptance

Issue: [#262](https://github.com/bcl1713/starlink-dashboard/issues/262). Pull
request: [#270](https://github.com/bcl1713/starlink-dashboard/pull/270), against
`dev`. Design and Native execution were approved on 2026-10-05.

## Behavior

The Missions dialog previews either a multiplier or a target runtime before
starting at the adjusted planned departure. Multipliers are inclusive 0.1–1000;
target runtime is at least one real second and must derive a supported rate.
Bodyless Activate retains its existing behavior. The backend owns the monotonic
replay clock, consumes every crossed canonical event, and stops at 100% and
POST_ARRIVAL without looping. Completion retains the selected leg.

Overview hides the five network cards and their header while a paced run is
confirmed running. Two independently visible windows share confirmed status
within three seconds. Four operational clocks use labeled simulated time;
observations, network history, ADS-B and freshness retain real time. Failed
refreshes freeze projection while retaining the running layout. Terminal states
restore the network cards and real clocks and retain a compact run result.

See [API contracts](../api/endpoints/simulation-run.md) and
[simulation-mode guidance](../setup/configuration/simulation-mode.md).

## Candidate and environment

Measured production candidate: `57494bf8120834e0e6e456444992e2516ba7af6c`. Merge
base with `origin/dev`: `8054b81fd474f70e1e1bd065a300c0092940f52f`. Evidence
directory:
`/tmp/starlink-262-evidence-57494bf8120834e0e6e456444992e2516ba7af6c`. This
local directory contains immutable candidate/image/runtime records, container
logs, per-case JSON, screenshots and videos; it is not a public URL.

The runner archives the clean candidate and uses its production Dockerfiles,
Nginx, normal single-worker `main:app` backend and isolated Prometheus. Browser
sources/config/assets come from the same archive. No paced API/time is
intercepted. Project `starlink-262` publishes only loopback frontend port 15262.
The actor's rootless Docker 29.8.1 daemon remains configured at
`unix:///run/user/1002/docker.sock`; no shared runtime configuration is changed.
Backend image Python is 3.11.17, Node 22.22.2 and Playwright 1.63.0. Chromium is
153.0.8010.12 on Linux 7.0.0-34-generic, Intel i9-10900K (20 logical CPUs),
using ANGLE Vulkan SwiftShader rendering. Image digests are retained in
`images.txt` beside the candidate SHA and Compose configuration.

The timed KML has a 20-minute window, varying 300/600/300-second segments, and
crosses the dateline. Its adjusted departure is 01:00 UTC. Golden fixture
expectations independently define X/Ka/Ku/AAR outcomes. A controlled Ka coverage
GeoJSON makes coverage deterministic. ADS-B is disabled. The live rejection case
launches the real app with hardware connection, telemetry and
public-IP/geolocation discovery forced disconnected. The initial live attempt
exposed missed discovery paths; the corrected run passed the live controls and
had no external discovery URLs in its retained logs.

## Measured results

| Journey                     |     Measured real time |   Lateness | Events / result                        |
| --------------------------- | ---------------------: | ---------: | -------------------------------------- |
| Target runtime, 120 seconds |           120.002035 s | 0.002035 s | 21, final arrival                      |
| Fixed multiplier, 10×       |           120.001744 s | 0.001744 s | 21, final arrival                      |
| Long fixture, 1000×         |            12.001395 s | 0.001395 s | 22, final arrival                      |
| Slow fixture, 0.1×          | 1.785399 s observation |          — | 0.178540 simulated s                   |
| Running propagation         |             143.557 ms |          — | Independent Overview context           |
| Completion propagation      |             992.791 ms |          — | Both visible contexts                  |
| Cancellation / direct route |                 Passed |          — | Restored cards / cancelled run         |
| Backend restart             |                 Passed |          — | New incarnation, idle, no active flags |
| Controlled live rejection   |                 Passed |          — | Both paced entry points                |

All completed runs must finish at the exact route endpoint, 100%, POST_ARRIVAL,
X satellite Paced-X-3 and final X/Ka/Ku offline states. The normal fixture
consumes 21 events; the long fixture consumes 22. Deterministic tests separately
check simultaneous-event ordering, delayed multi-event ticks and repeated reads.

All six production cases passed on this candidate, including actual backend
restart and live-mode 409 controls. Cleanup passed. Inspection of desktop,
responsive, fullscreen and restored screenshots plus decoded video frames
confirms the corrected 1920×1080 native window is captured without cropping.

The target journey records desktop 1920×1080, responsive 390×844 and native
fullscreen screenshots, plus explicitly sized 1920×1080 videos from both
contexts. It checks the same Canvas instance, follow preference, effective-route
geometry and retained aircraft trail. Offline refresh failure freezes all four
clock strings and preserves hidden cards; recovery resumes projection.

## Verification

Before implementation, backend had 1610 passing tests and frontend had 949.
After the product fixes, full backend verification passed 1707 tests with 20
skips and two existing warnings; frontend passed 1000 tests and its production
build. Canonical static verification passes formatting, lint, Markdown/link
checks and acceptance typing policy checks. New harness/config contracts were
observed failing before implementation and then passing.

Existing controlled globe/camera/route/arrival/traffic/history browser
regressions passed 59 checks with the default cadence. Two pre-existing history
fixtures advance five seconds per response and require at least four seconds
between requests; they initially failed at the base branch’s one-second default
and pass separately at the documented five-second rollback cadence. These
diagnostic checks remain separate from real Nginx acceptance.

The report commit is followed by an exact-final-head production rerun, static
gates and applicable GitHub CI. Its external evidence is linked in PR #270 to
avoid changing the candidate merely to embed its own SHA. Independent review and
final CI status are also recorded in the PR; this report alone does not certify
a later head or authorize merge/deployment.

## Failures corrected during acceptance

- The first fixture applied adjusted departure before importing KML; import
  clears that setting. The fixture now adjusts after import and asserts it.
- Actual timed KML can omit a timing profile. The paced private route now
  materializes its window before adjusting departure; source data remains
  unchanged. Regression tests use the imported fixture.
- React Query paused offline polls. The run query now attempts them while
  offline, reports failure and freezes projection; a query contract and real
  two-window test cover it.
- The browser journey assumed an existing Exit fullscreen button. The app uses
  native fullscreen; acceptance now exits through the native browser API.
- Default video sizing cropped resized/fullscreen content. Explicit recording
  dimensions now preserve the desktop frame; the config contract covers them.

- Live activation checked for a simulation coordinator before checking mode,
  returning 503 rather than 409. The mode guard now runs first, covered by a
  regression without a simulation coordinator. The initial live fixture also
  missed telemetry and public-IP discovery; its behavioral guard now verifies
  all external discovery is disconnected before loading the real app.

Earlier failed candidates and traces remain diagnostic evidence. Their cleanup
logs confirm project resources and the port were released on failure.

## Independent review and fix pass

One fresh whole-branch review found seven important issues and no critical
issues. One tested fix pass addresses duplicate/rounded nonpositive segment
durations with route validation, rejects unavailable selected diversions,
accepts distance 100% during a timed stationary terminal segment, wakes the
producer on committed activation, decodes structured error messages, presents
confirmed status in Missions, and retains monotonic age for unchanged producer
observations after backward UTC corrections. Focused tests were observed failing
then passing; the full backend suite passes 1715 tests (20 existing skips),
frontend passes 1013, and production build/static gates pass. Exact-head CI and
production proof follow this commit. The runner now uses a 30-second ordinary
interval and a two-second target to test wakeup, and keeps the initiating window
in Missions through completion.

Three minor presentation findings are deferred: initial 10× versus specified 1×
and missing immediate-departure explanation; live-mode entry control remains
visible while actual start is blocked; independently polled arrival presentation
can briefly lag Completed. The PR records them for the next review decision. The
earlier exact-head static CI job passed code/Markdown checks but timed out on
five existing CelesTrak documentation links; this external failure is not a
product-test failure. Final CI is rerun without suppressing those checks.

## Scope and limits

Completion lateness measures publication after the monotonic deadline; normal
acceptance allows at most one second. Operating-system suspension and overloaded
hosts can delay publication, so the API reports actual lateness rather than
promising hard real-time execution. Slow pacing is checked for a bounded
observation, rather than waiting hours for full completion. Provider coverage
boundaries and live hardware are outside this controlled acceptance lane.

Restart must create a new runtime incarnation, report idle and clear active
flags without resuming. Cancellation and direct-route deactivation must restore
panels. Cleanup logs prove no `starlink-262` containers/volumes or port 15262
listeners remain; the feature worktree stays available for the open PR.
