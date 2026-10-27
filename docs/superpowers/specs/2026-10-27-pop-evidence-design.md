# PoP evidence and forecast reconciliation

Implement issues #417, #418 and #419 together because observation identity feeds
live reconciliation and map/export presentation. Preserve forecasts, planning
outage semantics, and normal service availability. Use synthetic evidence only;
no deployment or live mission changes.

## Approach

Resolve identity at the backend boundary using the nine operator-supplied IPv4
CIDRs, with catalog coordinates and explicit operator-static provenance. Retain
raw provider GeoIP as separate evidence. GeoIP-only city aliases may support
tentative forecast comparison but must never be presented as verified identity.
UI-only relabeling would leave metrics and exports inconsistent; geographic
snapping would invent identity.

Resolver evidence includes sample and lookup times, bounded freshness, canonical
identity source, raw provider values and discrepancy. Revalidate successful
GeoIP at 15 minutes, retry failures at 60 seconds, and expire unsampled IP
evidence after 30 seconds. IP changes immediately invalidate old coordinates. No
network operation is permitted by a read-only consumer.

Reconcile occurrence IDs in route order. A fresh destination can resolve a later
occurrence while explicitly superseding missed predecessors; repeated unchanged
samples cannot complete re-entry occurrences. Expired windows become unconfirmed
forecast history, not ongoing imminent interruption warnings. Preserve expected
times, first observed time and residual where available. Unknown or stale
observations cannot complete occurrences. Revision changes reset lifecycle.

Overview retains existing POIs and concise advisories; Operator exposes identity
source, GeoIP, time/freshness and disagreement. CSV fields explicitly describe a
mission snapshot, never leg-time history. Known-prefix marker coordinates come
from the existing sourced catalog even when GeoIP disagrees or fails.

## Required mappings

Los Angeles: 216.255.176.0/24, 216.255.182.0/24. Ashburn: 216.255.177.0/24,
216.255.183.0/24. Dallas: 216.255.178.0/24, 75.78.128.0/24. Sydney:
216.255.179.0/24. Frankfurt: 216.255.180.0/24. Tokyo: 216.255.181.0/24.

## Verification

Test CIDR boundaries/nonmembers/malformed input, contradictory and failed GeoIP,
same-IP correction, mapped/unmapped changes, stale evidence,
early/skipped/re-entry/revision transitions, API/map/metrics/export consistency
and frontend warning copy. Run synthetic rendered-browser map/Operator checks
and production-path controls where the configured Docker runtime permits. Report
any unavailable acceptance accurately. Push feature branch and open PR against
dev; retain open-PR worktree and stop all task resources.
