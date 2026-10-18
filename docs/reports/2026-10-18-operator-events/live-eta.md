# Airborne restriction ETA — PR #379 review correction

Reviews 6249927777 and 6249975666 superseded acceptance of mission-plan UTC for
in-flight restriction notifications. The implementation now reuses existing live
route-aware ETA calculations for transport restriction boundaries. The
[updated timing specification](../../superpowers/specs/2026-10-18-operator-live-eta-design.md)
defines the integration and acknowledgment behavior.

## Operational result

At injected UTC **16:45**, forty-five minutes after planned departure, the
existing X model's restriction starts at planned **16:01**. Operator instead
shows live **16:53:00** (about eight minutes ahead), with no cue yet. Increasing
current speed changes the existing blended route ETA to **16:49:00** (about four
minutes ahead). Its displayed UTC and five-minute notification threshold update
together; both desktop and mobile attempt one browser tone. The same geographic
occurrence and notification generation survive the ETA update.

Preflight retains planned UTC. Early airborne departure uses live timing even
before the planned departure. Deviation/rejoin and revised geometry use existing
route projection. Zero/unavailable live speed produces unknown live timing and a
visible source reason; obsolete planning UTC remains reference data only.
Airborne PoP windows continue to come from the actual #348 live producer.

## Exact production qualification

Candidate: `4fdb318b5dc9da36335aefe0f4e6b98b2e2ed6b3`. Both images are built
from that committed archive using the production Dockerfiles; Nginx serves
ordinary HTTP. All inputs are synthetic raw route, position, speed, phase,
coverage and catalog inputs, never injected event/prediction outputs.

All four browser scenarios passed: existing display controls/Overview, actual
nonsecure LAN HTTP, normal modeled foreground alerts and the delayed-flight live
ETA case. Desktop 1920×1080 and mobile 390×844 show the live restriction card
within the viewport; the original workflow also covers landscape 844×390.

- [Exact image/archive identity and complete cleanup](live-eta/summary.json)
- [Live ETA, cue and displayed-time assertions](live-eta/live-eta-proof.json)
- [Desktop live restriction](live-eta/live-eta-1920.png),
  [mobile live restriction](live-eta/live-eta-390.png)
- [Multiclient and recovery browser proof](live-eta/model-alerts-proof.json)
- [All four qualification groups](live-eta/qualification.json)
- [LAN HTTP](live-eta/events-lan-http.json),
  [acknowledgment crash/backup recovery](live-eta/events-backend.json),
  [existing display behavior](live-eta/displays-proof.json)
- [Selected artifact hashes](live-eta/hashes.json)

Actual #349 export controls, unchanged telemetry ZIP/planning CSV content,
read-only/full storage media, crash recovery and backup/restore all passed. The
runner removed every owned container, network, volume, listener, child process,
image and temporary build tree. Raw evidence and ownership records are retained
at `/tmp/issue-368-live-eta-4fdb318b`.

## Regression and review evidence

Eleven native live-timing tests pass, including exact late/early departure,
varied speed, Ka boundary timing, deviation/rejoin, sample-bound publication,
acknowledgment across a large ETA move/restart, and nonresurrection after
passage. The full frontend suite passes **1,830 tests** with two workers. The
production build, canonical static gate and **25 acceptance/ownership harness
tests** pass. Full backend: **4,136 passed, 20 skipped**. Product code is
identical between that full-suite run and the exact production candidate; later
changes affect only test assertions and documentation. Counts and log hashes are
retained in [verification.json](live-eta/verification.json). Submitted-head
checks are in
[PR CI](https://github.com/bcl1713/starlink-dashboard/pull/379/checks).

Independent review found two Important issues: preflight overlap matching could
override geographic identity, and stale fallback could restore planned PoP
windows. Both were reproduced failing, corrected and pass regressions. Its Minor
finding requested visible unavailable/out-of-window browser checks; those now
pass. No findings were deferred. Unchanged background delivery/routing controls
remain outside this revision; the existing export compatibility was exercised.

The first production run failed a deviation/rejoin assertion that assumed a
fixed two-second difference despite different projected positions. The revised
check compares rejoining the original position with its original ETA. A second
passing run exposed screenshots of the drawer's top rather than the restriction;
the final run adds scrolling and an explicit in-viewport assertion. These were
test/evidence corrections; prediction results were never altered to pass.

## Decisions

- Reuse existing boundary geometry and ETA physics. No new transport prediction
  engine, flight-delay offset or confidence gate is introduced.
- Keep optional acknowledgment across live timing updates of the same geographic
  restriction. This avoids repeat warnings from forecast refreshes; a changed
  route/boundary or sustained higher severity can establish a new alert.
- Retain immutable accepted estimate history rather than recording every refresh
  as a durable event. Passed boundaries classify active/ended model windows;
  their capture time is not claimed as an observed crossing or outage.

Sound/vibration remain best-effort while Operator is open. Browser evidence
proves an oscillator attempt, not physical speaker output. This qualification
makes no aircraft-readiness claim. PR #379 remains draft and unmerged.
