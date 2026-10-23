# Diagnostic network correction

Authorized only for offline implementation by
[orchestrator checkpoint 6364263800](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6364263800),
following the isolated Forge experiment at
`dfb4f8675d34d28d5c930da03bb2aae6ff9c74aa`. Starting PR head:
`134cbcd3005eca0eeb6a1bb35d1bff91cf58d793`.

The diagnostic Compose generator now sets `networks.default.internal: false`.
This is a third correction layer after the accepted logging/Node and frontend
readiness corrections. `network-overlay.json` binds its predecessor and exact
replaced/current source hashes. The comparison pins that manifest separately,
regenerates the original plan byte for byte first, then accepts exactly the A/C
base network hashes and existing logging override hashes. All other plan fields,
source trees, image labels, receipts and configuration fields remain checked.
Historical rendered configurations retain `internal: true`; they are not
rewritten. Compose v5 omits false defaults in rendered output; this omission
means false.

The bridge is no longer egress-isolated. Containers can use ordinary bridge
egress; loopback publication does not restrict outbound access. No credentials,
ports, external networks or service network attachments are added. All three
services use only their task-owned default bridge. There is no attachment to
unrelated Docker networks; this does not promise that routable host services are
unreachable. The exact full rendered comparison checks this topology, loopback
host bindings, CPU/memory/PID limits, bounded local logs and unchanged images.
The frontend HTTP readiness gate and 78/90/10-second deadlines are unchanged.
The 1.5-second observer requirement remains unchanged.

This correction applies only to the separately generated diagnostic
configuration. Production Compose, application source, Dockerfiles, original
frozen build plan, closed receipts and historical failure evidence are
preserved. No application or browser startup, image build, A retry, C execution,
benchmark, calibration or soak is authorized. Stop for checkpoint review after
offline verification and push.

Offline verification and exact hashes are retained in
[network-correction evidence](../perf391-network-correction-v1/evidence/verification.json).
