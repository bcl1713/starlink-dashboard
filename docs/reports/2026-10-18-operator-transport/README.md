# Operator transport decisions verification

Issue #369, epic #361, [PR #380](https://github.com/bcl1713/starlink-dashboard/pull/380).
The user approved the design and plan and selected native execution. This report
records implementation and review evidence; merging requires separate approval.

The Operator page now records atomic decisions containing multiple services,
with independent Intended, Requested, Reported Applied and Operator Checked
reports. Optional timing, reasons and relationships support retrospective entry
and corrections. Previous revisions remain immutable. Actual routing remains
unknown; a report or check never establishes the SDR/OSPF path.

Advisory review uses the existing guarded event snapshot and its live route-aware
ETA sources. It shows preparation, calls, conferences and customer participation
alongside restrictions. Changes during active communications warn without
blocking saves. No new predictor, routing control or Overview redesign was added.

## Production simulation

Tested candidate: `f72c9be4e88c84ac820b097d9d668925367bf112`. The production
Dockerfiles and Nginx served the compiled application over HTTP. All inputs are
synthetic; these results establish software behavior, not aircraft readiness or
actual routing. Exact image identities and the source archive hash are in
[acceptance.json](acceptance.json).

The bounded runner used project `starlink-operator-369-transport`:

```sh
timeout --kill-after=20s 90m python3 tools/acceptance/operator-journal/run.py \
  --candidate f72c9be4e88c84ac820b097d9d668925367bf112 \
  --project starlink-operator-369-transport \
  --evidence /tmp/starlink-operator-369-evidence-final --transport
```

All qualification groups passed. [Browser assertions](transport-proof.json)
cover applied-only entry, independent reports, multiple services, retrospective
correction, unknown actual routing, active-call advisories, concurrent clients,
lost committed response, offline/reconnect, cross-mission decisions, link removal
and restore, nonsecure LAN HTTP, stale sources, live ETA and restart. Viewports
were 1920×1080, 390×844 and 844×390. [Existing ETA assertions](live-eta-proof.json)
exercise delayed/early departure, changing speed, deviation/rejoin and revised
routes through the existing real prediction interfaces, using raw synthetic
inputs rather than fabricated predictions.

[Backend durability](transport-backend.json) records seven decisions and nineteen
immutable revisions, backup/restore with recovered links, and two-service crash
barriers before and after commit. Retrying creates exactly one atomic decision;
children are reaped. [Existing compatibility controls](qualification.json)
include storage failures, acknowledgment recovery, mission CSV and telemetry
package preservation with a transport decision present. Broader mission-package
integration remains separate work.

- [Desktop review and decision](transport-1920x1080.png)
- [Portrait review and decision](transport-390x844.png)
- [Landscape review and decision](transport-844x390.png)
- [Desktop immutable history](transport-history-1920.png)
- [Portrait immutable history](transport-history-390.png)
- [Unavailable or stale review](transport-unknown.png)
- [Desktop live ETA](live-eta-1920.png) and [portrait live ETA](live-eta-390.png)
- [Existing customer Overview](display-overview-1920x1080.png)

Screenshots capture the scrolled workflow; JSON assertions establish the full
scenario. [Normal journal projection](normalOperationsExample.json) and
[historical Operator Checked revision](operatorCheckedHistoryExample.json) are
actual synthetic records read back from the accepted production container.

## Local verification and review

The canonical backend tier passed **4,169 tests**, with 20 skips and one existing
cartopy warning. The canonical frontend tier passed **1,844 tests in 269 files**
and the production build. Four-CPU affinity bounded Vitest concurrency in this
workspace. The final acceptance-harness and populated-schema group passed
**26 tests**. The populated schema-002 migration includes revision history,
active links, an acknowledgment and an intentionally advanced SQLite sequence;
all survive schema-003 upgrade. Static checks include formatting, Ruff, ESLint,
Markdown, internal links and the repository acceptance policy. External ADS-B
link warnings remain nonblocking under existing policy.

An independent whole-branch review found three issues, each reproduced before
fixing: planned change timing masked reported application timing; completed
participation was omitted from historical correlation; and missing records after
an old-store recovery could leave an editor blocked. All were corrected and
regression-tested. A subsequent compatibility regression verifies that empty
check-replacement metadata does not change old accepted command hashes.

Other implementation decisions retain existing behavior: use the existing UUID
fallback for ordinary LAN HTTP, expire stale captures with a one-shot timer,
retain frozen retry identities across reload/store changes, and preserve #362's
dependency conflicts rather than silently clearing links. Identical displayed
review messages are grouped without merging distinct restriction identities or
changing the underlying assessment rows.

## Upgrade, backout and cleanup

See the [operations guide](../../operations/operator-transport.md) for schema
upgrade, backup, restore and backout. Earlier migrations remain unchanged;
upgrade validates the preserved journal before committing. Do not run an older
writer against a schema-003 database.

The runner's [cleanup result](acceptance.json) confirms no remaining task
containers, networks or volumes and removal of its images, listener and child
processes. Raw bounded-run logs remain under the evidence directory in `/tmp`.
The open PR worktree and branch are retained for review; shared runtime resources
and primary-checkout files were preserved.
