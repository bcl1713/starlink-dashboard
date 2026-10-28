# Overview Bloom Experiment Plan

**Goal:** Deliver issue #429's isolated, offline laptop experiment; never merge
or deploy it. **Spec:**
[Issue #429](https://github.com/bcl1713/starlink-dashboard/issues/429) (approved
experiment). **Baseline:** origin/dev `f0c1bd49` (includes #428).

This is the explicitly requested experiment/spike. Use the approved
straightforward RenderPass → UnrealBloomPass → OutputPass design first.
Emission-range separation is the first approach; an emission selection pass
would add scene rendering cost and is deferred unless the visual review
demonstrates it is needed. No new postprocessing dependency. No production
entrypoint or configuration changes.

1. [ ] Standalone build/loopback server, CSP and runtime guards; no API modules,
       credentials, persistent settings or operational fixtures. Reuse current
       scene components with default context = A. Bundle existing Earth/mask
       assets.
2. [ ] Composer owner at positive R3F priority in all modes: A calls renderer
       once, diagnostic/B call composer once. Allocate on entry; dispose on
       exit; resize main targets at unchanged renderer DPR, then bound bloom
       targets.
3. [ ] B-only HDR city/core/particle emission and removal of fake halos.
       Preserve particle pools, picking, geometry occlusion, semantic colors and
       A defaults.
4. [ ] Synthetic fixed sun/route/POIs/traffic/weather specimen, fixed-step
       seeded particle replay and repeatable camera path. Mode switches preserve
       scene; explicit replay resets only camera and simulation. Small
       experiment controls.
5. [ ] Bounded timing capture with warm-up, sample counts, median/p95 intervals,
       renderer identity, draw-buffer and bloom sizes, resources, SHA and
       JSON/CSV. Screenshot workflow stays separate. Record user-supplied laptop
       power mode.
6. [ ] Focused lifecycle/guard/material/replay tests, frontend lint/type/build,
       cold browser launch with internet denied and local request-only
       whitelist, screenshots and switch/resize checks. Produce run sheet and
       limitations.

Review focus: far-side features, resize/DPR changes, interrupted measurements,
repeated mode switches, browser networking escape routes, matching particle
workload. Cloud software rendering is smoke evidence only. Full-overlay fixture
is representative synthetic geometry, not all operational data systems. Laptop
A→B→A repetitions and owner review cannot be performed by this cloud session.
