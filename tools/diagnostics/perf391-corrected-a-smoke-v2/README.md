# Corrected original-A smoke: STOP at preflight

**No runtime executed. Stop for checkpoint review on draft #408.**

Session: NEW — LOCAL FORGE, 2026-10-23. Starting commit:
`8c95eecb93fd5f37d9d6150008168682a5ba514d`.
Authority: [orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6372603348).
Task branch: `diag/perf391-corrected-a-smoke-20261023`, created from origin/dev
and advanced to the requested starting commit in an isolated worktree.
Primary checkout stays clean on dev.

One preflight invocation failed; there were **zero A executor invocations, zero
C invocations, zero context regenerations, zero application starts, zero browser
launches and zero screenshot attempts**. The work/outer/forced-grace policy stays
78/90/10 seconds. Five scheduled 1 Hz source/host observations, one network chart,
maximum one screenshot bracket and the 1.5-second observer gate remain unchanged;
none was exercised by this invocation. No runtime or performance pass is claimed.

## Failure and exact boundary

Reason: `RETAINED_LAUNCH_ABSOLUTE_WORKTREE_PATH_MISMATCH`.

The task's preflight harness additionally invoked the existing
`perf391-corrected-a-runtime-v2/verify.py` in the new worktree. At line 20,
`assert compile_launch() == launch` failed: its retained launch is tied to the
prior worktree's absolute paths. Adding this path-specific verifier to the new
worktree's preflight was an operator harness mistake. The new harness did not
reach the approved context regeneration or bound-executor selection steps.

Read-only diagnosis found exactly five changed string fields: browser-owner
command path and corrected identity's build-plan, executor-adapter, lineage and
receipt paths. Every difference is exactly the old worktree prefix replaced by
the new one; the retained launch was not edited or normalized to pass. See
[failure diagnosis](evidence/failure-diagnosis.json),
[actual failed command log](evidence/host-check-16.log),
[preflight traceback](evidence/preflight.log), and
[command/PID ledger](evidence/commands.json).

The first failed prerequisite triggered STOP as instructed. No fix, preflight
retry, alternate activation, identity-guard bypass or A/C execution followed.
The read-only diagnosis recomputed an offline launch comparison only. It did not
call `bound_executor()` or its coroutine. No evidence establishes a defect in,
or inability to activate, the validated executor binding. Its CLI rejection
remains intact. No new runtime entry point was added or run.

## Verified capabilities and unavailable boundaries

- Private CPython 3.11.16 environment: six approved wheel URL/hash identities,
  every installed wheel payload, native rpds identity, validator/Registry and
  HashTrieMap functionality, and dependency compatibility passed. PYTHONPATH was
  unset and user-site packages disabled. The environment is now removed.
- Existing corrected retained validator passed before the launch comparator:
  correction provenance, historical and v2/compatible-v1 receipt lineage,
  retained asset/module closure and retained dependency/build evidence. This
  revalidates retained evidence; it does not rerun compiled fixtures or prove
  live browser behavior.
- Forge host namespace: PID 1 systemd, actor UID 1002, configured
  `unix:///run/user/1002/docker.sock`, context default, Docker 29.8.1/rootless,
  overlayfs, cgroup v2. Ports 38080–38083 bound successfully in preflight and
  were independently clear after cleanup. Available disk was 24,505,659,392 bytes;
  memory 55,168,512,000 bytes, above the original 4/6 GiB thresholds. Cgroup limits
  are retained. The managed environment-status tool and policy snapshot were
  unavailable; no readiness is inferred from them.
- Cleanup preservation audit freshly inspected all eight historical/corrected
  image IDs and compared tags, digests, configuration, rootfs, OS and architecture
  with retained inventories. All matched; no image was built, pulled or changed.
- All 5,548 pre-existing tracked files remain byte-identical to the requested
  starting commit, including historical evidence and all validated source guards.

Fresh stopped-image extraction, actual Node 22.22.2/Playwright 1.63.0/Chromium
revision 1243 distribution checks, regenerated corrected context, effective
three-layer Compose verification, and process-Owner exercise were **not reached**.
Their historical qualifications remain historical. No claim is made that this
invocation completed those prerequisites.

HTTP readiness, actual browser attachment, chart visibility, history-response →
retained/projection → actual uPlot commit chain, stable frontend Finish, correlated
plot commits, backend final export, stream summaries and runtime loss accounting
are **unavailable: NO_RUNTIME_STARTED**. There was no backend or browser state to
preserve and no backend export to collect before teardown. Screenshot reason is
`NO_BROWSER_STARTED`, with zero attempts. Missing evidence is not treated as zero
loss. Original A's historical failure remains; C remains NO-GO.

[Outcome and capability boundaries](evidence/outcome.json) ·
[preflight checks](evidence/preflight.json) ·
[private Python validation](evidence/dependency-command-03.log) ·
[wheel hashes](evidence/wheels.json) ·
[source preservation and identity hashes](evidence/source-preservation.json).

## Hashes

| Artifact | SHA-256 |
| --- | --- |
| Retained reviewed launch (not executed) | `f15d657727bd029e54233e783cfa1acdf18f6889c7180f9dba4158c4182ce0e2` |
| Binding identity overlay | `78e44168dceeeaad82bbcd2ced9a0d92aabcae554ebb02cf775b431904f7c6c9` |
| Corrected build plan | `7b96a51d675b9b9c26787dfa06c2fe8458816b0088b2568e6707d6b5a7de7ca7` |
| A lineage receipt v2 | `785b24fc61fdd196ac64e9dd2ae1afd39b7210c73acbc711b614f39ab8235725` |
| A compatible-v1 receipt | `eba5c87d4e619a5468e96b6829d52c4ed0d24bff115ce043551cc6399a0281d4` |
| Historical build plan | `8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5` |

Selected corrected A backend:
`sha256:87a2379218610bd64b4e9e332a0d1bd70ed3fabe673c0dee8c865950d5fc9747`;
frontend:
`sha256:f3d62a630ea1c8be51a609b611a50d1e3725a7f2f8d83d530dea6ff78f3b9df5`.
These are preserved images, not running containers from this invocation.

## Cleanup and publication

[Independent cleanup audit](evidence/cleanup.json) verifies every recorded
PID/start identity absent, no scoped process survivors, listeners, containers,
networks or volumes, and all eight image identities unchanged. The private venv,
wheels and cache were removed after evidence preservation. The context/runtime
roots and lock were never created. [Independent post-removal host verification](evidence/post-cleanup.json)
confirmed absence again. Preflight tool session 57259 completed with exit 1;
setup and cleanup commands exited 0. No task runtime resources remain. Only the
open-review worktree and committed evidence remain.

Sandbox Docker/Git access restrictions were handled with approved host commands,
preserving actor configuration. No approval rejection occurred. No application,
daemon or Nginx changes, image build/pull, packet capture, calibration, benchmark,
sustained test, merge, deployment or issue closure occurred. PRs #403/#405–#408
are open/draft/unmerged; #404 is an open issue, not a PR. #390/#391 remain open.

[Artifact manifest](artifact-manifest.json) closes this additive package.
`verify-evidence.py` checks the closure, actual failure, diagnosis, zero runtime
counts, source preservation, private dependency checks, unchanged policy and
cleanup evidence. It does not retry any preflight/runtime work. **STOP for
checkpoint review on #408.**
