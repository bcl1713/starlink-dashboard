# Overview weather detail production acceptance

Issue [288][issue] now uses native camera demand to acquire actual higher-zoom
observed precipitation, with matched coverage masks and a complete zoom-2
fallback. Radar opacity is 0.40, selected from populated operational-overlay
comparisons. RainViewer remains the initial adapter after the bounded
[source comparison](2026-10-06-weather-source-comparison-results.md).
International observed coverage and the free-source operating choice remain.

## Production behavior

The canvas observer captures camera matrices and drawing-buffer dimensions,
runs visible-tile selection and stabilization, then forwards `DetailDemand`.
Demand samples at most four times per second, stabilizes for 400 ms and holds
at most eight regional radar/mask pairs. Native wheel, touch, rotation,
follow/reset and projection offsets retain their existing behavior.

The backend publishes source-neutral capabilities and product identity.
`product_id` derives from stable source/product/schema/coverage/dimension and
capability fields. Human-readable provenance remains informational; wording
changes update presentation without invalidating downloads. Canonical XYZ and
product validation run before provider DNS or dialing.

Coarse work retains priority within four active exchanges, two detail exchanges,
90 total and 30 detail attempts per rolling minute. Two pending positions and
four acquisition-pool positions remain available to coarse work under detail
saturation. Browser work uses four operations, at most two for detail, and a
96 MiB owned decoded-allocation ceiling. Complete and detail textures use
32+16 MiB; detail disposes before coarse replacement, retaining the 48 MiB peak.

Pair publication requires both decodes and current displayed-frame identity.
Lifecycle cancellation closes late resources. A current pair's 45-second
deadline enters bounded cooldown and retries stationary demand. Detail failure
retains the eligible coarse frame without changing observation age. Settings,
visibility, connectivity, frame expiry and coverage midnight remain authority
for acquisition and presentation.

## Rendered comparisons and recorded sources

Candidate `4f03d852095bc09636bb265e1fdefe6b10a63cdd` passed the focused native
detail/touch/opacity scenario in 2.8 minutes. Twenty-four views cover four
factors (0.35, 0.40, 0.45, 0.72), desktop 1920-by-1080, fullscreen and mobile
390-by-844, with native lighting and dark lighting. Real V2 mission creation,
timed KML upload and leg activation supply route, departure/arrival POIs and
labels; aircraft, track, GEPs, borders and telemetry remain present.

All views were inspected. 0.40 keeps precipitation recognizable while reducing
its weight over the globe. 0.35 is slightly faint on the small view; 0.45 adds
weight without a useful readability gain; 0.72 obscures underlying globe detail.
Coverage hatching remains separately 0.17. No slider or weather interaction is
added to Overview.

The focused view acquired six actual level-3 pairs from native selection,
accounted for 60 MiB peak owned decoded resources and 48 MiB GPU storage, and
passed native touch zoom plus detail-error coarse continuity. These are owned
resource dimensions, not total browser RSS or a hardware performance benchmark.
Chromium uses ANGLE/Vulkan SwiftShader in this environment.

Candidate `a04ae72bfa30549e257a96a79fd315c66ad6fc91` passed the alternate-source
and dated RainViewer replay scenarios. A normalized fixture advertises a
different source, attribution and maximum zoom 5; the same production selector,
pair owner, scheduler and shader consume it without provider URL parsing.

Actual U.S. RainViewer PNGs were observed at 02:30 UTC on 2026-10-06 and
captured at approximately 02:36 UTC. Saved hashes and timestamps remain intact.
An advancing fixture weather clock starts at that recorded capture epoch, so
production freshness and expiry checks remain active. A bounded recorded
level-5 demand passes through production owners and resolves additional pixels
against the saved complete fallback. Eight pairs use 64 MiB owned decoded
resources and 48 MiB GPU storage. Native selection is verified independently
with geographic fixtures. This historical replay does not establish live
provider availability or native selection for that captured regional subset.

## Verification and delivery evidence

The complete local backend suite after reliability corrections passed 1,881
tests, with 20 skips. All 1,154 frontend tests passed. The production frontend
build, lint and TypeScript checks passed. Nine acceptance/typing-policy tests
passed. Canonical-path, source-identity, cancellation, memory, queue saturation,
deadline recovery, stale/expiry and coverage-midnight regressions remain in
the deterministic suites.

One fresh whole-branch review found coarse admission saturation, lost stationary
timeout recovery and a rendered boundary-test gap. The first two received
failing regressions before their fixes. The native boundary regression also
reproduced missing hatching beside a fading absent neighbor; its shader fix
retains that neighbor's absence mask before removing the coarse seam.

Final delivery requires the unfiltered six-scenario acceptance on the committed
PR head plus all three exact-head CI gates. [PR 289][pr] records the delivered
SHA and final results. Focused earlier runs above are evidence for specific
behaviors, rather than substitutes for that final gate.

Local immutable bundles live below
`.superpowers/sdd/issue-288-weather-detail/evidence/`. Each production run stores
`candidate-sha.txt`, image IDs, archived-source ownership, browser pixels and
screenshots, provider stream events, logs, and cleanup records. The final bundle
is `production-<delivered-SHA>`. Failed experiments remain separately named.
The runner's exit trap stops only the task's Compose project and verifies
containers, networks, disposable volumes, source archive and loopback listeners
are gone. Open-PR worktree and evidence remain for review.

See the [feature documentation](../features/overview-weather.md),
[normalized endpoint contract](../api/endpoints/overview-weather.md) and
[acceptance runner](../../tools/acceptance/overview-weather/README.md).

[issue]: https://github.com/bcl1713/starlink-dashboard/issues/288
[pr]: https://github.com/bcl1713/starlink-dashboard/pull/289
