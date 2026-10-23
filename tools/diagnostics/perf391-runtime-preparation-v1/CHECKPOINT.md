# Runtime preparation checkpoint for #391

**Ready for preparation review; NO-GO for builds or runtime.** Starting delivery
is `cd734117cb5580ef2579145c99d1cc30aeae9451`; instrumentation remains the
tested `051870c738d9ab72338852ea848918a35a663094` source. This commit adds only
the separate runtime-preparation package. It does not alter Stage 5's release,
original A/C revisions, collector #407, frozen v2 or customer application code.

Read the [design](README.md), [future runbook](RUNBOOK.md),
[build plan](evidence/offline-final/runtime-build-plan.json), and
[actual Forge preflight](evidence/forge-preflight.json).

## Results and exact prepared identities

- Two independent guarded exports produce byte-identical build plans,
  Dockerfiles and Compose configurations. All **621 frozen files / 97 source
  entries** verify; effective A/C hashes remain unchanged.
- **10/10 offline tests** pass, including source/overlay drift, wrong labels,
  wrong collector/role/plan, Node floor, changed/extra/symlink assets, missing
  compiled modules and disabled launch execution.
- Two Node syntax checks, the original probe/new alias TypeScript no-emit check,
  two dry launch plans and two Compose config renders pass. All **10 owned
  validation commands** pass. Synthetic receipt fixtures certify no image.
- Scoped Ruff E4/E7/E9/F, direct Black API equality, authored Prettier and
  Markdown checks pass. Broad Stage 5 Ruff debt is unchanged; no canonical CI
  waiver.
- Independent source review closed eight Important findings across two review
  rounds and found no remaining Critical/Important preparation finding. It did
  not build images or run runtime proposals.

| Prepared identity                            | SHA-256                                                            |
| -------------------------------------------- | ------------------------------------------------------------------ |
| Build-plan file                              | `8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5` |
| Runtime overlay inventory                    | `5b3b36938d43d5ade1b9bb67d32dd6bf36b5f80d8f298b475ef732e794ba965c` |
| Frontend runtime source/config closure (A=C) | `5dcf2b6ace61440516fc695f4bcab4d8da487e0612f80a864dd6669bab641695` |
| A complete generated context                 | `9563d8f4396323fc2ba726605704fb41a14c56c89010d55a2b48cfa1d412f7ab` |
| C complete generated context                 | `a13a56cd0ddf80059c6d3b2ae389f627700421a1060d530534c239f488e1dcd6` |

Generated JSON evidence is retained byte-for-byte; formatting does not silently
invalidate its manifest/config identities. All compiled-asset hashes, diagnostic
image IDs and installed build dependency results remain **unavailable/unbuilt**.

## Actual feasibility and outstanding gates

Actor Docker is healthy on the inherited rootless socket: Docker 29.8.1, Compose
5.5.1, systemd/cgroup v2. Host PID/cgroup and network inventory is readable
through approved host execution. The host exposes 20 CPUs, but the actor's
ancestor quota is **10 CPUs**. Planned ports 38080–38083 and 38180–38183 were
free at inventory time; no reservation or future container mapping exists.

Playwright 1.63.0 and Chromium revision 1243 are installed; existing type
definitions support the disposable APIs, and ELF dependencies resolve. Actual
launch, sandbox compatibility, document lifecycle, screenshot behavior and probe
overhead remain untested. Host Node 22.12.0 fails the app's 22.22.2 floor;
explicit Python 3.11.16 exists. Future execution requires a reviewed compatible
Node/interpreter/dependency environment and actual immutable built receipts.

The actor has no effective packet-capture capability or tcpdump file privilege.
Raw browser body/wire provenance remains unavailable. No unbounded Playwright
response-body or CDP fallback is allowed. Parsed-history and chart input can
qualify separately; a stable owned PNG can establish only a sampled compositor
result. Stage 3B remains deferred.

## Proposal for the next review

Request a separate build/receipt review, then at most **one A and one C smoke**,
serially, with **five** source/host samples at 1 Hz per role, one visible
latency panel, a first chart evidence slice and one screenshot attempt. Five is
below the checkpoint's 30-sample ceiling. End browser admission early to respect
the unchanged 64-artifact limit. The 1.5-second observer-cadence rule is
unchanged.

Each role has a 78-second work deadline, 90-second outer timeout and 10-second
forced grace. A failure, unavailable required identity, loss, missing final,
missing successful history-to-chart request join or cleanup failure stops before
C; no retries or alternate transport. The exact proposed argv, private Compose
projects, budgets, startup order and recovery commands are in the runbook and
generated A/C plans. Runtime code remains a reviewed proposal, not a tested
launcher or production/performance equivalent.

## Cleanup and stop

The offline and static owners retain **13 PID/PGID/start records**, all reaped
and clean. The host audit verifies 15 identities including their parent owners.
The exploratory export, both final export trees and temporary typecheck/test
paths were removed. Two exploratory formatter CLI runs reached their wall
limits; host checks found no survivors before switching to a passing
single-process Black API check. The execution ledger records these failures.

Final host verification records scoped empty Docker listings, no task listeners
or task process survivors and absent temporary paths. No images, services,
browsers, application HTTP, captures or performance runs were started. Preserve
the isolated open-PR worktree and evidence. Primary checkout stays on `dev`.

Stop after publishing this checkpoint to draft #408. Keep the other diagnostic
PRs draft/unmerged and issues #390/#391 open. No merge, deployment or sustained
qualification is authorized.
