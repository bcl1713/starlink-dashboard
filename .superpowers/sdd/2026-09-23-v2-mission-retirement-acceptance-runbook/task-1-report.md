# Task 1 Report: Pure model and durable artifact contracts

## Status

Completed and committed as `910e53b49d5ff60a93fe90c3ebecb14896d29d1b` (`feat: add acceptance runbook artifact contracts`).

## Changed files

- `tools/acceptance/__init__.py`
- `tools/acceptance/model.py`
- `tools/acceptance/artifacts.py`
- `tools/tests/test_v2_acceptance_model.py`
- `tools/tests/test_v2_acceptance_artifacts.py`

No pre-existing untracked root reports were modified. No Docker, Compose, browser/Xvfb, network acceptance, push, or GitHub action was run.

## Delivered contracts

- Immutable `AcceptancePhase`, `AcceptanceInputs`, `PhaseResult`, and `RunManifest` model contracts.
- Strict full lowercase 40-character SHA, named-ref, evidence-root, and explicit phase validation; `full` is the default phase.
- Non-final enforcement for every phase except a passed `full` result.
- SHA-qualified, mode-restricted evidence directories with relative allowlisted artifact paths, sorted inventory, `manifest.json`, `SHA256SUMS`, and tamper-detecting checksum verification.
- Manifest records the phase classification plus independent primary and cleanup outcomes.

## TDD evidence

### RED

Command:

```text
pytest -q tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
```

Literal result before implementation:

```text
2 errors during collection
ModuleNotFoundError: No module named 'tools.acceptance'
```

The test imports were then aligned to the repository's existing `tools/tests/conftest.py`, which adds `tools/` to `sys.path` and therefore uses `acceptance.*` imports.

### GREEN

Command:

```text
pytest -q tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
```

Literal result:

```text
9 passed in 0.04s
```

## Quality checks

Commands and literal results:

```text
black --check tools/acceptance tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
All done! ✨ 🍰 ✨
5 files would be left unchanged.

ruff check tools/acceptance tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
All checks passed!

git diff --cached --check
(exit 0)

Added-line security scan for hardcoded credentials, shell injection, eval/exec, pickle deserialization, and interpolated SQL
(no matches; exit 0)
```

Required whole-repository test command was attempted:

```text
pytest -q
```

Literal result:

```text
2 errors during collection
backend/starlink-location/tests: google.protobuf.runtime_version.VersionError:
Detected incompatible Protobuf Gencode/Runtime versions ... gencode 7.35.1 runtime 6.33.6.
test_bounds.py: FileNotFoundError: [Errno 2] No such file or directory: '/app'
```

These collection failures are outside Task 1's changed files and occur before the Task 1 test modules run in the full suite.

## Self-review

- Confirmed each source and test module remains below 300 lines.
- Confirmed no production application, deployment, CI, credential, or runtime behavior was changed.
- Confirmed paths cannot escape the evidence root and manifest/checksum control filenames cannot be recorded as ordinary artifacts.
- Confirmed inventory ordering, `0700` directories, `0600` files, manifest checksum inclusion, and checksum tamper detection are covered by focused tests.
- Confirmed staged commit contains exactly the five Task 1 source/test files.

## Concerns

The full repository `pytest -q` baseline is not green in this environment because of the pre-existing `/app` assumption and incompatible installed protobuf runtime. Focused Task 1 tests, Black, Ruff, and staged-diff checks pass.

## Review repair (round 1/5)

### Findings addressed

- **Critical:** `RunManifest.with_outcomes()` and `RunManifest.to_dict()` now require every present result phase to match the manifest phase. A `runtime-cached` manifest therefore rejects a `full` final result before serialization and cannot emit final acceptance.
- **Important:** `AcceptanceInputs` now implements the `git check-ref-format --allow-onelevel` invalid-ref rules, including `..`, trailing `.`, `@{`, control characters, forbidden punctuation, leading-dot components, and `.lock` components.
- **Important:** `EvidenceWriter` records a trusted resolved artifact root and rejects symlinked artifact components and replacement/symlink traversal of the SHA parent before writing or verifying artifacts.
- **Minor assessed and addressed:** tests assert the SHA parent, artifact root, manifest, and `SHA256SUMS` modes.

### Changed paths

- `tools/acceptance/model.py`
- `tools/acceptance/artifacts.py`
- `tools/tests/test_v2_acceptance_model.py`
- `tools/tests/test_v2_acceptance_artifacts.py`

### TDD and covering checks

RED commands and literal results:

```text
pytest -q tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
14 failed, 9 passed in 0.13s

pytest -q tools/tests/test_v2_acceptance_model.py::test_cached_manifest_cannot_serialize_a_full_final_result
1 failed in 0.05s

pytest -q tools/tests/test_v2_acceptance_artifacts.py::test_writer_rejects_symlinked_sha_parent_outside_evidence_root
1 failed in 0.12s
```

GREEN command and literal result:

```text
pytest -q tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
25 passed in 0.06s
```

Covering test names include:

- `test_manifest_rejects_results_from_a_different_phase`
- `test_cached_manifest_cannot_serialize_a_full_final_result`
- `test_inputs_reject_git_invalid_refnames`
- `test_writer_rejects_symlinked_artifact_parent_outside_evidence_root`
- `test_writer_rejects_symlinked_sha_parent_outside_evidence_root`

Quality commands and literal results:

```text
black --check tools/acceptance tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
All done! ✨ 🍰 ✨
5 files would be left unchanged.

ruff check tools/acceptance tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
All checks passed!

git diff --check
(exit 0)
```

### Commit

- `7c361753aeabcd4b9718406e0d3e76dcf675be9c` — `fix: harden acceptance artifact contracts`

### Concerns

No Docker, Compose, browser/Xvfb, network acceptance, push, or GitHub action was run. The pre-existing whole-repository `pytest -q` collection blockers remain as documented above. Known root untracked reports were preserved.

## Review repair (round 2/5)

### Finding addressed

- **Important:** Before creating or chmodding the SHA-qualified directory, `EvidenceWriter` now checks a pre-existing `<evidence_root>/<sha>` symlink. If its resolved target is outside the resolved supplied evidence root, construction raises `ValueError`; no run directory is created and the external target mode is unchanged.

### TDD and covering checks

RED command and literal result:

```text
pytest -q tools/tests/test_v2_acceptance_artifacts.py::test_writer_rejects_preexisting_symlinked_sha_parent_during_construction
1 failed in 0.05s
Failed: DID NOT RAISE ValueError
```

GREEN and focused Task 1 test commands and literal results:

```text
pytest -q tools/tests/test_v2_acceptance_artifacts.py::test_writer_rejects_preexisting_symlinked_sha_parent_during_construction
1 passed in 0.04s

pytest -q tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
26 passed in 0.08s

black --check tools/acceptance tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
All done! ✨ 🍰 ✨
5 files would be left unchanged.

ruff check tools/acceptance tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py
All checks passed!
```

### Changed paths

- `tools/acceptance/artifacts.py`
- `tools/tests/test_v2_acceptance_artifacts.py`
- `.superpowers/sdd/2026-09-23-v2-mission-retirement-acceptance-runbook/task-1-report.md`

### Concerns

No Docker, Compose, browser/Xvfb, network acceptance, push, or GitHub action was run. The documented pre-existing whole-repository `pytest -q` collection blockers remain; focused Task 1 coverage is green. Known root untracked reports were preserved.
