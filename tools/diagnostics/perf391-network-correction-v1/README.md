# Diagnostic network correction — offline checkpoint

The only new Compose setting change is `networks.default.internal: true` →
`false` in the diagnostic generator. Draft PR #408 remains a checkpoint; no A
retry or C execution occurred.

Authority:
[orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6364263800).
Starting head: `134cbcd3005eca0eeb6a1bb35d1bff91cf58d793`. The controlled
experiment remains separately preserved at
`dfb4f8675d34d28d5c930da03bb2aae6ff9c74aa`.

The third correction layer pins predecessor and replacement source identities.
Original compiler regeneration matched the frozen plan byte for byte. Full plan
equality permits exactly four superseded fields: A/C base hashes for this
network change and A/C override hashes for the already accepted logging
correction. All other source, context, image, label, receipt and plan fields
remain identical. The full rendered configuration comparison permits the false
default (omitted by Compose v5), the existing validation project namespace and
explicitly resolved context paths only. Historical evidence and earlier
manifests were not rewritten.

## Exact SHA-256 identities

| Source                 | SHA-256                                                            |
| ---------------------- | ------------------------------------------------------------------ |
| `comparison.py`        | `0e8d276677f06aae04b688bf4dd5ba17d99c8760dcbd5c34344eb2369a34743e` |
| `network-overlay.json` | `fdbbc561f690f1dfb7d7c0dd65c476b60df8e6da9f8879fbca8a07ad89ebba15` |
| `prepare.py`           | `4f20ed461d36705918070b478485addeebe3bf4ded05bc1e1199d46e5637fa30` |
| `runtime_identity.py`  | `3664eaabcdbc434fd2ab4c73eee5a3952f235d7940c614eab34fe2acd8c4f164` |

Original frozen plan:
`8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5`.

| Role | Base config                                                        | Existing logging override                                          | Effective rendered config                                          |
| ---- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| A    | `591e4e381bb572b8284ee79a0cf0012a083aede83f4727dceca2662c5781a939` | `5419094df7e1bb5dbae1f0282aa0e4881d5a5f73e1b9c09fd83746d3fc36764c` | `70152ce569561e56c8ab2bbe85de103ded2497c1f19bda43b877790c0a02210e` |
| C    | `591e4e381bb572b8284ee79a0cf0012a083aede83f4727dceca2662c5781a939` | `ffdbe1293ea39e142752f56b438f12957dcd16fba22b546c2d8f4787446ca81e` | `2e67ff1d70813ee76fb60514796767a4be036ca7b3e9c5b7959245aea7d80edd` |

Exact rendered files retain their temporary path provenance; rerunning at a new
scratch path changes those rendered bytes. Source/base/override hashes and the
semantic full comparison remain deterministic.

| Role | Unchanged effective source                                         | Unchanged context                                                  | Closed receipt                                                     |
| ---- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| A    | `015c5f515438b7114f903e90c5c43014a2b29fb6c316fdbca0232681585c5baa` | `9563d8f4396323fc2ba726605704fb41a14c56c89010d55a2b48cfa1d412f7ab` | `7d337809082015880bb51e69bcf8973fd5036518286b876dda77145543c9c24f` |
| C    | `4f1913894101595ab96bdd289bd80f88a6dcb95c058d0851cb3e4e025ae13f4a` | `a13a56cd0ddf80059c6d3b2ae389f627700421a1060d530534c239f488e1dcd6` | `a9b7492aed2e90448d2ed8aeb4586dccd667d03e1cbb0829ff759a04537109e2` |

The complete approved before/after hashes are in
[comparison.json](evidence/comparison.json). Limits, loopback ports, image IDs
and provenance are in [verification.json](evidence/verification.json).

## Verification and security

Offline compiler/config verification passed using Python 3.14.4 and Compose
v5.5.1. Twenty focused existing tests passed: preparation 10, receipt/Node
identity 4, logging 1, deterministic readiness 4 and strict comparison 1. The
existing comparison case was extended for the network delta and rejects reverted
internal mode, added networks, service attachments, image changes and unrelated
plan drift; no new test functions were added. Retained
receipt/assets/dependencies/image recipes and frozen release revalidation passed
using the approved runtime-overlay validator in place of the historical-only
overlay validator. Independent code review reported no actionable findings.
Whitespace checks passed.

Two broader process-owning tests each hit their explicit 120-second limits: fake
executor cleanup and the TERM-resistant readiness probe. Their failures are
retained in `evidence/*timeout*.log`; these tests are not claimed passing. Host
inspection confirmed each old process tree absent before another run, and their
exact owned scratch directories were removed. The latter retained owner manifest
reports its child stopped/reaped. The helper's initial path-selection error and
corrected rerun are also retained. No runtime correction was attempted in
response.

All three services use only their own default bridge. The bridge now permits
ordinary egress: loopback publication restricts inbound host bindings, not
outbound reachability. No credentials, ports, external network attachments or
production changes were added. No assurance is made that routable host services
are unreachable. Backend limits remain 2 CPU/2 GiB/256 PIDs; Prometheus 1 CPU/1
GiB/256 PIDs; frontend 0.5 CPU/256 MiB/64 PIDs. Local logging stays 10m/one
file/compress=false, immutable image references and frontend HTTP readiness
remain unchanged. The 1.5-second observer requirement and 78/90/10-second
runtime deadlines are intact.

## Cleanup and stop

The [independent host audit](evidence/host-audit.json) verifies all four
accepted image IDs, labels and RepoDigests unchanged. Actor socket
`unix:///run/user/1002/docker.sock`, context `default`, Forge rootless Docker
29.8.1 were preserved. Scoped A/C, experiment and render-only project
container/network/volume lists are empty. No task listeners, processes or
temporary compilation roots remain. Shared
volumes/daemon/configuration/credentials are untouched.

Offline tool sessions: 90516 (initial helper failure), 62187 (bounded broad-test
timeout), 1710 (bounded readiness process-test timeout), 33038 (final offline
verification, exit 0). No application, browser, HTTP probe, image build/pull, A
retry, C run, benchmark, calibration, soak, merge or deployment occurred. The
only spawned test workloads were existing fake executor/process fixtures.
Open-review worktree/evidence are retained; runtime resources are absent.

#403/#405–#408 remain draft/open/unmerged; #404 is an open issue rather than a
PR. #390/#391 remain open. **Stop for checkpoint review.**
