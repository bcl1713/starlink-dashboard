# Tasks 1–2: Model/artifact contracts and Compose reconciliation

Companion to
[2026-09-23-v2-mission-retirement-acceptance-runbook](2026-09-23-v2-mission-retirement-acceptance-runbook.md).

## Task 1: Pure model and durable artifact contracts

**Files:**

- Create: `tools/acceptance/__init__.py`
- Create: `tools/acceptance/model.py`
- Create: `tools/acceptance/artifacts.py`
- Create: `tools/tests/test_v2_acceptance_model.py`
- Create: `tools/tests/test_v2_acceptance_artifacts.py`

**Interfaces:**

- Produces `AcceptancePhase`, `AcceptanceInputs`, `PhaseResult`, and
  `RunManifest` used by Tasks 2–4.

- Produces `EvidenceWriter(root: Path, sha: str)` with `record_json`,
  `record_text`, `finalize_manifest`, and `verify_checksums` used by Task 4.

- `AcceptanceInputs.from_mapping(mapping)` rejects missing/invalid values before
  side effects. `full` is the default phase.

- [ ] **Step 1: Write failing model and artifact tests**

```python
def test_inputs_require_full_sha_and_named_ref(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="40-character"):
        AcceptanceInputs.from_mapping({"sha": "0437a0bb", "ref": "feat/x"})


def test_runtime_cached_cannot_be_final_result(tmp_path: Path) -> None:
    result = PhaseResult("runtime-cached", "passed", final_acceptance=True)
    with pytest.raises(ValueError, match="non-final"):
        result.validate()


def test_writer_rejects_paths_outside_sha_root(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, "a" * 40)
    with pytest.raises(ValueError, match="outside"):
        writer.record_text(Path("../escape.txt"), "no")
```

- [ ] **Step 2: Run focused tests to verify RED**

Run: `pytest -q tools/tests/test_v2_acceptance_model.py
tools/tests/test_v2_acceptance_artifacts.py`

Expected: FAIL during collection because the acceptance modules do not exist.

- [ ] **Step 3: Implement immutable validation and evidence writer**

```python
class AcceptancePhase(StrEnum):
    PREFLIGHT = "preflight"
    STATIC = "static"
    BROWSER_CARD = "browser-card"
    RUNTIME_CACHED = "runtime-cached"
    FULL = "full"


@dataclass(frozen=True)
class AcceptanceInputs:
    sha: str
    ref: str
    evidence_root: Path
    phase: AcceptancePhase = AcceptancePhase.FULL
```

`EvidenceWriter` creates `<root>/<sha>/<run-id>` with mode `0o700`, writes only
relative allowlisted paths with mode `0o600`, records sorted inventory entries,
writes `manifest.json` and `SHA256SUMS`, and verifies checksums with the
artifact
root as the checksum working directory. Its manifest records phase
classification
and both primary and cleanup outcomes.

- [ ] **Step 4: Add deterministic artifact boundary tests**

```python
def test_manifest_inventory_is_sorted_and_checksum_valid(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, "b" * 40)
    writer.record_text(Path("z/result.txt"), "z")
    writer.record_text(Path("a/result.txt"), "a")
    manifest = writer.finalize_manifest(RunManifest.minimal("b" * 40, "feat/x"))
    assert [item["path"] for item in manifest["artifacts"]] == [
        "a/result.txt", "z/result.txt"
    ]
    writer.verify_checksums()
```

- [ ] **Step 5: Run focused tests to verify GREEN**

Run: `pytest -q tools/tests/test_v2_acceptance_model.py
tools/tests/test_v2_acceptance_artifacts.py`

Expected: PASS.

- [ ] **Step 6: Commit the independently testable foundation**

```bash
git add tools/acceptance/__init__.py tools/acceptance/model.py \
  tools/acceptance/artifacts.py tools/tests/test_v2_acceptance_model.py \
  tools/tests/test_v2_acceptance_artifacts.py
git commit -m "feat: add acceptance runbook artifact contracts"
```

## Task 2: Isolated Compose and BuildKit reconciliation

**Files:**

- Create: `tools/acceptance/compose.py`
- Create: `tools/tests/test_v2_acceptance_compose.py`

**Interfaces:**

- Consumes `AcceptanceInputs`, `EvidenceWriter`, and `PhaseResult` from Task 1.
- Produces `render_override(inputs) -> str`,
  `parse_buildkit_log(text, expected_tags) -> list[ImageRecord]`, and
  `reconcile_build(result, log, inspect_tag) -> BuildDisposition`.

- Task 4 invokes `build_full`, `start_no_build`, `runtime_controls`, and
  `cleanup_compose` through this module only.

- [ ] **Step 1: Write failing topology and reconciliation tests**

```python
def test_override_replaces_root_fixed_ports_and_private_env_file() -> None:
    override = render_override(_inputs())
    assert "!override" in override
    assert "5173:80" not in override
    assert "container_name:" not in override
    assert "env_file:" not in override
    assert "STARLINK_MODE=simulation" in override


def test_nonzero_wrapper_with_two_completed_images_is_reconciled() -> None:
    log = _complete_log("accept-backend:sha", "accept-frontend:sha")
    disposition = reconcile_build(
        returncode=124,
        log_text=log,
        expected_tags=("accept-backend:sha", "accept-frontend:sha"),
        inspect_tag=lambda tag: "sha256:" + tag,
    )
    assert disposition.usable is True
    assert disposition.wrapper_anomaly is True


def test_missing_unpack_is_not_reconciled() -> None:
    assert reconcile_build(124, _log_without_unpack(), _tags(), _inspect).usable is False
```

- [ ] **Step 2: Run focused tests to verify RED**

Run: `pytest -q tools/tests/test_v2_acceptance_compose.py`

Expected: FAIL during collection because `tools.acceptance.compose` does not
exist.

- [ ] **Step 3: Implement isolated Compose construction and parser**

Render a task-owned override outside the repository. It starts only
`starlink-location` and `mission-planner`; it replaces inherited ports and
container settings, uses task-owned bind paths/volumes, and supplies non-secret
values derived from `.env.example`. Implement a strict BuildKit parser requiring
for both expected tags: exporting, naming, unpacking, final DONE, and successful
`docker image inspect` ID. Return an explicit disposition instead of retrying.

```python
def compose_build_argv(inputs: AcceptanceInputs, compose_files: list[Path]) -> list[str]:
    return [
        "docker", "compose", "--project-name", inputs.project_name,
        *sum((["--file", str(path)] for path in compose_files), []),
        "build", "--no-cache", "--progress=plain",
        "starlink-location", "mission-planner",
    ]
```

- [ ] **Step 4: Add fake-Docker sequencing test**

```python
def test_genuine_build_failure_never_starts_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_fake_docker(monkeypatch, build_returncode=2)
    result = run_full_build(_inputs(), _writer())
    assert result.status == "failed"
    assert all(" up " not in call for call in calls)
```

- [ ] **Step 5: Run focused tests to verify GREEN**

Run: `pytest -q tools/tests/test_v2_acceptance_compose.py`

Expected: PASS.

- [ ] **Step 6: Commit Compose/build boundary**

```bash
git add tools/acceptance/compose.py tools/tests/test_v2_acceptance_compose.py
git commit -m "feat: add isolated acceptance compose controls"
```

[Return to the main
plan](2026-09-23-v2-mission-retirement-acceptance-runbook.md).
