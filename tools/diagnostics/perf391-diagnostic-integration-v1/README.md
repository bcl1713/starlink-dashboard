# Perf391 diagnostic integration v1 — Stages 1–2

Stage 1 implements offline contracts and source/build guards only, authorized by
[the #408 orchestrator review](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6350554670).
The approved design is at `8aa7791bb03f0573cf602bdbfe8e43c085ee2325` in
[the integration plan](../../../docs/superpowers/plans/2026-10-22-perf391-diagnostic-integration.md).
Stage 2 backend integration is now implemented under the later checkpoint
authorization; see [Stage 2 evidence and limits](STAGE2.md). Image builds and
runtime collection still require separate authorization. The exporter never
imports application modules; offline tests execute guarded source slices.

## Contract

`contract.json` fixes phases, outcomes, capabilities, omissions and projection
policy. `integration-event-schema.json` is a closed Draft 2020-12 boundary-event
schema; `contract.py` performs schema and stream validation. Compatible v1
non-boundary records remain in the immutable collector's own stream. This is not
an emitter or a replacement integration analyzer.

Events carry bounded run/operation/span/process/thread/clock identities,
decimal-string nanoseconds, explicit outcomes and allowlisted scalar identity
fields. Null identity needs an unavailable reason. Browser native TID/thread
start/CPU stay null. A has no immutable frame, final-authority or CAS evidence.
Only C's successful ready-frame tick/replay CAS can project
`producer.published`. Gaps, backwards clocks and identity reuse are rejected
rather than repaired. Navigation/restart requires a new stream and clock.
Missing capabilities default to unavailable. Declared source capability does not
imply installed probes.

## Offline source guards

`build.py` exposes functions only; it cannot build images or start services.
Full references are fixed in `PINS`, including C's final head separately from
its implementation reference, collector source separately from release metadata,
and the frozen harness. All Git subprocesses have a 60-second timeout.

- `verify_role` rejects short/wrong/role-swapped SHAs.
- `verify_clean_worktree` checks exact HEAD, tracked, untracked and ignored dirt
  when a future caller accepts a worktree input. Exports use immutable Git
  objects directly and never copy mutable worktree contents.
- `export_source` writes a new isolated Git tar and source directory only;
  existing destinations fail. `verify_export` compares the complete file set,
  bytes and executable modes to the role's pinned archive. Symlinks and special
  files are deliberately unsupported and fail closed.
- `verify_equivalence` checks identical A/C frontend trees and C final-head
  runtime inputs against the implementation reference (backend, frontend, tools,
  monitoring, scripts and root Compose inputs).
- `reference_files` / `verify_dependency` compare complete collector and frozen
  comparator inventories. `verify_collector_release` verifies the pinned release
  manifest against executable source; `RESULTS.md` is the release's explicitly
  excluded metadata, still included in source inventory protection.
- `apply_patch` requires a reviewed patch SHA-256, whole base-tree hash, exact
  target file set and per-file preimage/postimage hashes. It applies text hunks
  at their stated lines with full context. Drift, offsets, fuzz, binary changes,
  rename/delete/create, mode changes and no-newline patches fail closed. It
  validates all hunks before writing, then checks the complete effective tree.
  Only backend application Python, the exact approved backend `main.py`, and
  frontend `src` TypeScript are eligible; Dockerfiles, lockfiles, configuration,
  collector and comparator paths fail.
- `verify_frontend_patch_agreement` compares reviewed A/C frontend target and
  preimage/postimage hashes, allowing their backend patches to differ.
- `verify_primary` rejects diagnostic imports in primary application inputs;
  callers must also verify the exact unpatched role export.

Future derivative preparation must verify the base export, frozen dependencies
and reviewed patch pair before applying either patch, then retain the complete
returned file inventory and tree hash. Patch specifications are review inputs,
not hashes generated from an unreviewed patch immediately before use. Stage 1
ships no actual A/C patches. Stage 2 adds backend-only A/C patches and
reviewable hash specifications without widening frontend scope.

`build-manifest-schema.json` and `validate_manifest` define an offline build
input record. It identifies ancestry and effective base independently, source,
collector, harness, archive, patch and effective tree hashes, and seven required
labels (including the retained OCI base revision). `manifest_template` supplies
an explicitly unbuilt record: image digest and compiled assets remain null. The
schema rejects claims of a built image at this stage. Stage 2+ must extend
reviewed artifact inventories and verify actual image labels/digests after
separate build authorization; validating desired labels proves no image exists.

## Reproduce Stage 1

Use Python 3.11 and a private environment with `requirements-test.txt`. From
this package, with that environment active:

```sh
timeout --kill-after=10s 10m python3 -m unittest discover -s tests -p 'test_*.py'
timeout --kill-after=10s 10m python3 verify.py --output artifacts/identity-new
```

The output directory must be new. `verify.py` retains exact A/C tar archives,
source trees, complete per-file SHA-256/mode/size inventories, dependency
inventories and `identity.json`. The committed evidence summarizes the retained
ignored `artifacts/identity/` export. Inventory hashes use canonical sorted
JSON; tree hashes hash canonical file records. Archive hashes hash literal Git
tar bytes, independently compared a second time to the pinned Git archive.

`evidence/` contains initial red runs, review failure reproductions, final green
results and export identity evidence. `evidence/SHA256SUMS.json` hashes all
package review inputs/evidence except itself and ignored caches/artifacts.
Private outputs are isolated; no application build/browser/capture/benchmark
command is present. Tests use `TemporaryDirectory` for synthetic dirty sources
and patches, and leave no service or process owner alive.

## Next checkpoint

Stage 1 was accepted. Stage 2 now supplies the authorized backend hooks and
offline per-role equivalence tests. Stop for Stage 2 checkpoint review before
Stage 3; see [the Stage 2 report](STAGE2.md). Conditional capture
privilege/topology is a later adapter gate, not a backend prerequisite.
Browser/capture, owner/host integration and offline integration verification
remain subsequent stages. Runtime/calibration needs a separate decision. Frozen
acceptance gates, the 1.5-second threshold, draft PR states and open #390/#391
remain unchanged.
