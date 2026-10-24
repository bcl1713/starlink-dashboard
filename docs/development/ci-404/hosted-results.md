# Hosted backend CI results

Normal PR run
[40066349301](https://github.com/bcl1713/starlink-dashboard/actions/runs/40066349301)
used feature head `0ce08bf034ac356544ddf49088fea63326e0d9a3` and actual merge
checkout `b629c1d1fe6d023e7cb9ded75056b4f2e4497b2c`. All seven jobs succeeded.
Each shard collected 4,300 cases; their disjoint union passed 4,280 with exactly
the original 20 item skips, zero collector skips, and the original case outcomes
preserved after the explicit two-ID rename. All five added offline controls
passed.

| Job                          |                        Cases selected | Pytest seconds | Job seconds |
| ---------------------------- | ------------------------------------: | -------------: | ----------: |
| Backend shard 1              |                                   936 |        213.443 |         238 |
| Backend shard 2              |                                  1225 |        141.895 |         163 |
| Backend shard 3              |                                   989 |        166.361 |         191 |
| Backend shard 4              |                                  1150 |        195.978 |         226 |
| Backend Test Gate            |                       4300 reconciled |              — |          10 |
| Static Quality Gate          | Existing policies and tools contracts |              — |         177 |
| Frontend Test and Build Gate |                    Existing full gate |              — |         198 |

Backend wall time is the earliest shard start through aggregate completion,
including the scheduling gap before the aggregate. All four shard jobs
overlapped for 163s. Their owners completed both canonical commands, reported no
surviving processes/listeners, and removed their private roots before artifact
upload. Every shard reported CPython 3.11.17, uv 0.12.19, the same complete
100-entry distribution multiset, identical relevant source/input hashes, and a
cache hit. The full distribution digest is
`e3852bafc424f5ac8309c1f36fdad2886c27bae2e48cf482bd0604ad9bfcf722`.

The 20.050 execution runner-minutes sum all seven job intervals; they are not a
billing estimate. This is 0.667 more than the 19.383-minute historical three-job
reference, with unmatched host/tooling inputs. Four isolated runners duplicate
startup and full collection, while eliminating the serial critical path. The
failed qualification round additionally consumed 19.000 execution runner-minutes
and remains separate from accepted repeatability samples. GitHub's usage API
reported zero billable milliseconds for that run, which is not evidence of zero
resource use or a dollar cost. Final repeatability requires the same backend,
observer, runner, verifier, configuration, lock, interpreter, and complete
distribution identities; documentation-only Git heads may differ.

The [implementation report](completion.md) retains the measured serial baseline,
coverage rules, canonical commands and rollback. The second comparable round and
final exact-head acceptance are recorded in
[PR 411](https://github.com/bcl1713/starlink-dashboard/pull/411).

The [committed summary](evidence/hosted-clean-1-summary.json),
[raw artifact archive](evidence/hosted-clean-1.tar.gz), and
[checksums](evidence/hosted-clean-1-manifest.json) retain the first accepted
sample independently of GitHub artifact expiry.

A [host cleanup audit](evidence/local-host-cleanup.json) found all 909 recorded
local PID/start identities absent, private runtime paths removed, and no active
checkout claim. The open-PR worktree and acceptance evidence remain retained.
