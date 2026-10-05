# Mission-leg simulation speed acceptance contract

This is a required companion to the
[simulation speed design](2026-10-05-mission-leg-simulation-speed-design.md) for
[issue 262](https://github.com/bcl1713/starlink-dashboard/issues/262). Both
documents and Native implementation were approved on 2026-10-05. Product
implementation and acceptance are in progress.

## Verification and documentation

Use deterministic injected real/monotonic clocks and route/event fixtures for
behavioral tests. Cover:

1. Equivalent 10× and 120-second pacing for a 20-minute leg; explicit 1× and
   slower-than-real-time replay; inclusive supported boundaries.
2. Start at adjusted planned departure; multi-speed segments, missing
   intermediate anchors, effective derived route, and coherent
   position/speed/time/ETA output.
3. Multiple and simultaneous events in one tick, zero/end boundary events, every
   transition committed once in order, repeat polling, and same-leg restart.
4. Exact final coordinate, 100% progress, POST_ARRIVAL, and no loop/reverse
   wrap.
5. Invalid schema/numbers, unsupported derived rates, missing/invalid timing,
   changed preview/plan, live-mode bypass attempts, and rollback on failed
   start.
6. Real observation-age behavior, failed collection, stale run snapshots,
   backward wall-clock changes, monotonic advance, and correct simulated
   countdown labels.
7. Switching, deactivation, deletion, incompatible edits, config/mode change,
   startup/shutdown, terminal retention, and obsolete response rejection.
8. Dialog keyboard/error behavior, preview accuracy, confirmed status
   propagation, all five network cards/header hidden only during paced running
   state, stale status retention, restoration, and preserved
   globe/trail/timing/camera intent.

Run affected backend/frontend contracts, the repository's applicable full-suite
and static checks, and existing route/history/arrival/camera/link regressions.
The implementation stage records product tests separately from this acceptance
contract. Establish the product baseline before implementation.

For product acceptance, verify the exact candidate SHA through an isolated
production Docker/Nginx/backend path using the actor's configured Docker daemon.
Use controlled fixtures instead of live dish/provider traffic. Record an actual
120-second run plus a fixed-multiplier run, all event outcomes and final phase,
two-window status/layout propagation, cancellation and restart, deadline error,
screenshots of running and restored panels, responsive/native-fullscreen
behavior, and task-owned cleanup. Long-leg/high-rate fixtures must show bounded
work and no skipped events. Keep unverified results pending and obtain
independent review.

Document both input modes and formulas, supported limits, valid-timing
requirements, immediate planned-departure start, simulated versus real time,
hidden/restored network panels, final state, cancellation/restart behavior,
deadline limitations, API errors, and unchanged bodyless activation. Update
simulation-mode guidance, mission-planning/Overview guidance, affected API docs,
and an exact-SHA acceptance report.
