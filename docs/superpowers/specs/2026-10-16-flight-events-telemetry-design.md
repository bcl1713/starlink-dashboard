# Flight events and durable mission telemetry

Status: design approved for planning; parking rule updated following user
clarification. No product implementation has begun.

## Purpose and agreed behavior

Correct misleading live arrival presentation and preserve the telemetry covering
the passenger's operational journey. Capture each planned leg from 30 minutes
before actual off-blocks through 30 minutes after first confirmed destination
on-blocks, including taxi out, flight, rollout, and taxi in. Preserve
off-blocks, takeoff, inferred landing, and on-blocks as separate UTC events.
These buffers were confirmed during discussion.

Normal planned legs remain separate. Ground duration alone never creates a new
leg. An operational refueling stop may remain within one planned leg, with
multiple flight segments and intermediate ground events. The operator must be
able to classify an ambiguous stop; an unexpected stop must not silently
complete the planned leg.

## Established code context and limits

Reviewed the default-branch flight state manager, flight status model, and
repository README. Existing phases are pre_departure, in_flight, and
post_arrival. Automatic departure currently uses speed above 50 knots for 10
seconds. Arrival requires 60 seconds within 100 metres of the route endpoint;
the supplied speed is unused in that decision. Detection tracks observation
freshness. Manual event triggers and route-reset behavior already exist.

The endpoint constraint plausibly explains missed arrivals away from the final
coordinate, but the complete live ingestion-to-Overview path has not yet been
diagnosed. Existing mission export preparation and Prometheus integration are
identified in the issue; their implementation and deployed storage configuration
still require inspection. This document proposes architecture, not a verified
end-to-end diagnosis.

## Recommended approach and alternatives

Use a persistent operational-event ledger, a detailed inferred movement state,
and incremental archival capture with Prometheus recovery. This separates
planned-leg identity, observed movement, and recording lifecycle.

Simply widening the arrival radius is smaller but cannot distinguish taxi,
parking, or intermediate stops. Querying the entire flight only after arrival is
simpler but leaves data dependent on Prometheus availability and retention until
that moment. Incremental capture costs storage and recovery logic but protects
the long capture window and restart behavior.

## Movement and event semantics

Track parked, taxi_out, airborne, probable_landed_rollout, taxi_in, and
parked_at_stop. Maintain uncertainty and telemetry freshness separately from
confirmed events. GPS-derived takeoff and landing are inferences, not exact
wheel-contact measurements.

Off-blocks requires sustained movement after a confirmed parked context; speed
alone cannot distinguish pushback, vehicle movement, and taxi in every case.
Airborne confirmation combines fresh position, speed progression, and altitude
trends when usable. Landing requires prior sustained flight and coherent
approach-to-ground evidence, using airport/route context without requiring a
100-metre endpoint match. Do not substitute absolute GPS altitude for runway
elevation. If evidence is insufficient, remain uncertain and permit manual
confirmation.

On-blocks requires sustained near-zero motion after a ground-arrival sequence,
with destination/ramp context where available. A taxi hold is a provisional stop
until the parking dwell is satisfied. Movement before confirmation resets the
candidate. Once parking is confirmed at the destination, later repositioning
does not revoke it or restart the capture tail. A DV offload stop counts as
parking even if a later move to a final stand follows. Later-movement
operational notes remain outside scope. Manual correction records the original
evidence and the correction instead of overwriting history.

Thresholds, dwell durations, airport-area boundaries, and altitude availability
must be established from the live signal contract and representative traces
before implementation. They are not asserted as validated values in this draft.
Detection gaps break candidate dwell continuity; duplicate or older observations
cannot advance it.

## Planned legs and operational stops

Bind every recording and event to persistent mission and planned-leg identities.
A leg contains ordered flight segments and ground stops. Route activation
changes do not reassign recorded observations or erase event history.

At the planned destination, the first confirmed parking starts the 30-minute
post-parking period. Away from the planned destination, retain an
intermediate-stop classification and continue the same recording until the
operator resolves continuation or completion. Permit explicit final-arrival
confirmation at a diversion airport. No automatic leg split based on elapsed
ground time.

If independent leg windows overlap, preserve each leg's requested time interval
with explicit shared time coverage; do not truncate or silently move samples.
This is a proposed edge-case default, since the user expects ordinary
turnarounds to be longer.

## Capture and durability

Maintain a rolling durable pre-event telemetry buffer so off-blocks detection
can recover the preceding 30 minutes. Capture available, allowlisted Prometheus
observations incrementally to backend-owned persistent storage, using
observation timestamps and resumable watermarks. Do not rely on process memory
or container-local ephemeral files.

Preserve original scrape resolution where available. Use bounded range queries
for initial buffer and recovery, with overlapping query boundaries and
deterministic sample deduplication. Record unavailable intervals and reasons. An
outage cannot be guaranteed recoverable if the source never collected data or
retention has expired; show the gap explicitly.

Persist event evidence, mission/leg association, capture boundaries, and pending
work. On restart, resume active captures and retry incomplete extraction. Use
idempotent jobs and atomic manifest publication. Finalize only after the first
confirmed destination parking buffer has elapsed and extraction is complete, or
publish an explicitly incomplete package with gap metadata.

For a long intermediate stop, keep the leg open and retain the ground interval.
Simulation and test observations use separately marked captures and cannot enter
an operational package. Disk exhaustion and collection errors surface capture
health and do not affect operational networking.

## Data and download contract

Version the CSV schema and metric allowlist. Include UTC observation time,
available aircraft position/altitude/speed, network measurements, and observed
public IP/ground-entry labels and coordinates when available. Missing and stale
values remain distinct from zero; retain source/freshness metadata. Do not
equate public internet PoP observations with physical RF gateways. Exclude
credentials and secrets.

A leg manifest contains mission/leg identity, ordered flight segments and ground
stops, event times and evidence, requested/available capture bounds, schema
version, metric provenance, gaps, correction revision, and file checksums.
Produce stable ordering and deterministic content for a sealed revision.
Corrections produce a new version rather than mutate an already downloaded
archive silently.

Extend existing mission export preparation with a distinct telemetry artifact
type. Preserve planning-export behavior. Completed mission ZIPs contain leg
datasets in mission order. Any package with pending legs or incomplete data is
clearly marked partial. Archives remain downloadable after Prometheus retention
expires.

## API and Overview compatibility

Add detailed movement state, event history, capture health, and completion
status through additive API fields. Preserve legacy phase values until consumers
are audited; derive compatibility phase from the detailed state rather than
immediately expanding an enum consumed elsewhere. Define legacy
departure/arrival timestamp mapping explicitly during the consumer audit to
avoid silently changing existing semantics.

Overview distinguishes estimated arrival, inferred landed/rollout, taxiing, and
confirmed parked. After a supported ground arrival, replace the recurring
positive arrival countdown with the ground state. Unknown or stale evidence
displays uncertainty. Audit independent ETA rounding/clamping as part of the
live-flow investigation. Display off-blocks separately from takeoff and first
confirmed destination on-blocks separately from landing.

## Verification and rollout

Verify the effective live ingestion, event, persistence, API, and Overview paths
before changing detection. Replay timestamped traces through the real live
detection adapter, alongside unit tests for state transitions and archive jobs.

Acceptance scenarios: two planned legs produce ordered independent archives with
both 30-minute buffers; long taxi and parking beyond 100 metres from the route
endpoint converge correctly; departure taxi is distinct from flight; a fuel stop
remains within one leg; a diversion can be explicitly completed; taxi holds do
not finalize; go-arounds and airport overflights do not land; stale, duplicate,
delayed, noisy, and missing observations do not invent transitions; absent
altitude yields uncertainty rather than certainty; route changes preserve
ownership; restart and Prometheus interruptions recover idempotently; retention
expiry does not remove archived files; simulated data stays segregated; manual
corrections generate auditable revisions.

Implement in stages: diagnose and improve event semantics and arrival
presentation; add persistent capture and recovery; integrate mission downloads.
Operational routing, bandwidth control, and PoP prediction remain outside scope.

## Review focus

User-confirmed: full departure/arrival ground phases, buffers relative to
off-blocks and first confirmed destination parking, and planned-leg identity
across possible operational stops. Proposed for review: operator resolution for
ambiguous stops, overlapping-window preservation, incremental capture, and
revisioned corrections. Live thresholds and compatibility mappings require
repository investigation and trace evidence before the implementation plan is
finalized.

## Confirmed parking clarification

A DV offload parking stop may last 30–45 minutes before repositioning. The user
explicitly selected the first confirmed destination park as the arrival
endpoint. Do not wait for the eventual storage stand or add DV-offload
classification. Later ground movement does not reopen the completed arrival or
extend its 30-minute recording tail. Intermediate operational stops away from
the destination still remain within the planned leg.
