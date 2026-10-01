# Overview #217 Departure and Arrival Plan

**Status:** Brian approved implementation of the proposed plan, including the
predeparture decisions below. Target `dev`; merge, deployment and issue closure
are outside this work.

**Baseline:** `dev` at `ef7844c84684511491525676adae24a5cbc603a3`, the merge of
PR #229. Implementation branch: `feat/217-arrival-states`.

## Approved behavior

Replace the five-row table with one compact panel using the existing
bottom-center placement and shared glass styling. Center the panel on the screen,
fit its content, center section text and divide paired sections vertically.
Sections stack with a horizontal divider when the available panel width is
narrow. Before flight, show only
**SCHEDULED DEPARTURE · name**, its effective mission schedule in UTC and an
hours/minutes countdown. After the scheduled time, show red elapsed text such as
**12 MIN AGO** or **<1 MIN AGO**, without a minus sign. Departure scheduling
includes configured adjustments and does not require GPS.

In flight, show **NEXT POI** and **LANDING · destination**, combining them when
the destination is next. Select the earliest upcoming event in route order,
including an untimed event ahead of a later timed one. Find the destination in
the complete response by `kind: arrival` and stable ID, never its name. Landing
countdowns remain nonnegative; only backend flight phase establishes landed.

Use **1 HR 39 MIN**, **39 MIN**, and **<1 MIN**. Remaining whole minutes round
up beyond the final minute; elapsed departure minutes round down. UTC labels use
**HH:MMZ**, including the date on another UTC day, with complete timestamps
accessible. Long names wrap; narrow layouts stack the sections.

## Implementation

- Add nullable collection provenance to internal position telemetry. Stamp valid
  live/simulated coordinates; preserve cache age. Invalid/default GPS positions
  remain unverified and do not enter movement trackers. Zero is a valid
  coordinate. Require fresh, verified positions and measured speed for automatic
  flight detection; telemetry gaps break departure and arrival persistence without
  changing confirmed phase. Distinguish measured stationary speed from the
  numeric compatibility zero during startup or recovery.
- Extend the existing endpoint with flight phase, effective scheduled departure,
  position collection timestamp and freshness state. Retain generated records
  for map context when in-flight estimates are unavailable. Suppress timing until
  speed has sufficient verified observations after startup or GPS/RPC recovery. Include
  same-sample
  route progress to distinguish passed destination from unknown eligibility.
- Derive panel state outside the view using the existing shared clock. Suppress
  timing on stale/invalid position or failed/expired arrival refresh. Missing
  mission, route, schedule, destination and estimates remain explicit.
- Preserve map markers and accessible names, including collision-hidden labels.
  Keep polling, charts, camera and fullscreen behavior. #218–#220 retain their
  satellite/legend, final composition and mobile-interaction scope.
- Update Overview and API guidance; annotate the responsive design with the
  approved predeparture amendment.

## Validation

Focused source/contract tests cover coordinate validity, genuine zero,
collection/cache timestamps, freshness boundaries, missing coordinator data,
actual coordinator speed recovery and metrics-to-phase detection continuity,
adjusted schedules and retained map records. Derivation/component tests cover
route ordering, identity, untimed events, destinations outside the old top five,
phase transitions, early/late departure, unavailable estimates and UTC rollover.

Run canonical backend, frontend and static gates against the pinned baseline.
Capture exact-candidate desktop ordinary/fullscreen and narrow browser evidence
for intermediate, destination-only, early/late departure, stale/missing and
landed states. Cover paired long countdown containment in 1500–1536px Overview
containers and across the panel stacking breakpoint. Retain metric-motion
and geometry regressions; review the updated
POI screenshot baseline. Run an isolated production-stack smoke test where
Docker access is available. Record source mode, renderer, SHA and limitations;
software rendering does not prove operator ten-foot readability.
