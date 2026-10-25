# Mission transport availability

Date: 2026-10-25

## Intent

Operators need to plan and continue a mission when X-band, Ka, or Starshield is
unavailable. A failed transport must stop contributing coverage and stop
producing future handovers, coverage transitions, POIs, and action reminders.
Recording an equipment failure must affect the mission immediately and persist
across legs and application restarts.

The user selected a shared availability model serving mission planning and the
operator dashboard, with mission defaults, leg settings, and failures effective
from now through mission end until explicitly restored. This design extends the
same behavior to all three transports.

## Approaches

Use one persisted mission availability model and one resolver for planning,
timeline preparation, live status, generated POIs, and operational events. This
is the selected approach: each consumer uses the same effective transport state.

A display-only filter would remove markers while leaving failed transports in
coverage and fallback calculations. Independent planning and operator settings
would allow those views to disagree. Neither satisfies the mission requirement.

## Planning behavior

Mission planning exposes X-band, Ka, and Starshield availability for the whole
mission. Each leg can inherit the mission setting or explicitly select available
or unavailable. The leg editor shows both its setting and the effective result.
The mission setting is a persistent default, including for subsequently added
legs; it does not silently erase deliberate leg overrides.

Available means eligible for the existing coverage and operating rules. It never
asserts connectivity or bypasses a coverage gap, manual outage, AR restriction,
or hard X-band constraint. Unknown Starshield PoP or handover evidence does not
make the transport unavailable.

Saving an availability change regenerates affected mission profiles through the
existing preparation/publication workflow. Both ordinary manual missions and
itinerary-managed missions support these settings. An unavailable X-band does
not require a selected satellite, permitted satellite list, or valid X geometry
to save or evaluate the remaining transports. Existing X assignments and locks
can be retained for later restoration, but are inactive while X is unavailable.
The optimizer must not propose X swaps for unavailable windows.

## Operator behavior

The operator dashboard has a prominent Transport availability section for the
selected mission, adjacent to service transport controls. Each transport shows
its effective availability and scope. For an active mission, Mark unavailable
applies from the current mission time through the remaining mission, including
subsequent legs. The primary action states this scope clearly. An optional
reason can describe the equipment failure; a reason is not required.

Restore ends that failure override at the current mission time. It returns the
transport to the underlying planned settings and existing coverage rules. A
transport planned unavailable remains unavailable after restoration. Failure and
restoration times remain in mission history. There is no automatic restoration
at leg change, midnight, reload, restart, or itinerary revision.

The existing installation-wide catalog enabled/archive fields continue to define
reusable assignment choices. A catalog toggle or a free-text issue is not
silently reinterpreted as a timed equipment failure. The dashboard makes the
mission availability action accessible without opening the catalog manager;
catalog help text directs operators to it when equipment is unavailable for a
mission.

An unavailable transport cannot be offered as a new service assignment. Existing
reported service assignments remain visible with an unavailable indication and
any resulting impact; failure must not fabricate an observed reroute.

## Shared state and resolution

Persist mission defaults, per-leg overrides, and an append-only history of
operational unavailability/restoration changes within the mission's owned data.
Use stable canonical keys X, Ka, and Ku internally, with Starshield in customer
and operator text. Keep catalog identifiers and names distinct from RF keys.

The resolver takes mission, leg, and an instant or evaluation interval. Planned
eligibility is the leg override if present, otherwise the mission default. An
active operational failure forces that transport unavailable regardless of the
planned setting. Restoration closes the operational failure; it does not alter
defaults or leg overrides. Existing physical and operating constraints then
further limit transports that remain eligible.

Use half-open intervals, including failure/restoration boundaries in the common
timeline grid. Preserve the existing manual outage windows and their semantics.
Operational failure timestamps use the authoritative mission clock, including
simulation mode, rather than the browser or host wall clock. Keep simulation and
live mission state isolated using the established run/lifecycle rules.

New fields have backward-compatible defaults. Existing missions retain current
behavior, including explicit legacy starshield_enabled=false. Resolve that field
as the prior planned Starshield setting when new settings are absent; document
and test precedence once new settings are saved. Availability must survive
package export/import and itinerary revisions, including new leg inheritance.
Import follows existing inactive-leg and operator-history rules; importing a
package never activates a mission or mutates another mission.

Writes use existing repository admission, atomic publication, and revision or
optimistic-concurrency guards. Reject stale changes instead of overwriting
another operator's update. Retry of an accepted command must be idempotent.
Mission availability must not depend on an enabled Operator journal store;
persist its own audit history and include it in the mission package.

## Calculations and displays

Apply effective availability before evaluating transport capability, backup
gaps, call continuity, outage duration, and X/Starshield concurrency. Turning
off Starshield releases only concurrency-only X restrictions, as today; it does
not release hard X restrictions. An unavailable X or Ka cannot protect a
Starshield transition window. Remaining usable Ka or coordinated
concurrency-only X still protect the plan under the existing continuity rules.

Retain generated POIs and their identities when availability changes. Mark
transport-related points inactive and hide them from active maps and upcoming
lists while their transport is unavailable. Restoring a transport makes its
still-relevant points eligible again without duplicate records. Recalculate
their applicability against the current route and plan; a past point must not
become an upcoming action just because the equipment was restored.

Publish active events only for actions that remain meaningful while that
transport is eligible. Suppress future X swaps and geometry warnings, Ka
coverage and handover events, and Starshield transition events within
unavailable windows. Do not delete the configured route, satellite records,
operator notes, or unrelated POIs. Keep departure, arrival, AR, weather, and
usable-transport events.

Recompute shared call-outage advisories from remaining capability rather than
blanket-hiding them. A single equipment-unavailable state or failure event may
remain visible to the operator; avoid repeated handover and coverage reminders
for a transport that cannot be used. Availability itself is not a service outage
when another usable transport maintains connectivity.

The generated POI store, saved timeline map_pois, planning preview, route maps,
Overview upcoming list, active satellite-link selection, operator event feed,
and exports must agree. Include availability revision in input identities and
cache invalidation. Retire superseded future event occurrences and local alert
cues through the existing event lifecycle; filtering only the browser is
insufficient. Past operator/event audit history is retained. Previously elapsed
mission intervals retain their prior modeled availability after an in-flight
failure.

Overview remains a customer-facing map: no new controls, diagnostics, or raw
timestamps. It reflects availability through existing links, POIs, and brief
advisories. Planning and operator views hold the detailed state and history.

## Validation and completion evidence

Test each transport independently, combinations, all unavailable, mission
inheritance, explicit leg overrides, and defaults for older missions. Cover both
legacy and itinerary planning paths. Prove X can be unavailable with an empty
satellite catalog, and verify Starshield/concurrency fallback behavior.

Exercise failure partway through a leg, subsequent leg activation, restoration,
restart, revision, package import/export, duplicate retries, and stale
concurrent writes. Verify unavailable assignments and impact indications without
changing historical service reports. Confirm pre-failure intervals and
historical events remain intact and no future transport-specific POIs, events,
or alert cues leak from saved or cached inputs.

Explicitly verify a fail/restore cycle keeps the affected POI records and stable
identities, changes their active applicability, and restores future applicable
points without duplicates or revived overdue alerts.

Use focused backend and frontend checks during implementation, followed by the
repository-required production-image and rendered-browser acceptance. Use an
isolated worktree, branch, and task-owned acceptance resources with explicit
timeouts and cleanup. Submit a PR against dev with evidence; retain its worktree
while open and stop its runtime resources after checks.

## Scope and implementation choices

This is one feature spanning the mission model, planner, operator controls, and
all consumers of generated transport state. It does not add hardware control,
automatic fault detection, recurring outage scheduling, or mandatory confidence
acknowledgments. Estimates and backup gaps never block saving a valid plan.

Builder choices include exact API route names, file/module placement, visual
arrangement within existing planning/operator sections, and the most economical
atomic persistence mechanism consistent with current repository patterns. The
precedence, temporal behavior, and consumer consistency above are required.
