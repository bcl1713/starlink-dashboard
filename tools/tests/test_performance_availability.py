"""The revised acceptance contract preserves the strict harness and registry."""

import copy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from acceptance.performance_availability.report import compare, summarize
from acceptance.performance_availability.state import NAMES, capture

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "tools/acceptance/performance_availability"


def test_adversarial_availability_contract():
    result = subprocess.run(
        [
            "node",
            "--test",
            str(HERE / "availability.test.mjs"),
            str(HERE / "monitor.test.mjs"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_strict_harness_files_are_unchanged_from_instrumentation_base():
    for path in (ROOT / "tools/acceptance/performance").iterdir():
        if not path.is_file():
            continue
        original = subprocess.check_output(
            [
                "git",
                "show",
                "33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96:"
                + str(path.relative_to(ROOT)),
            ],
            cwd=ROOT,
            timeout=10,
        )
        assert path.read_bytes() == original, str(path)


def test_state_adapter_uses_one_immutable_head_without_collecting_registry():
    from prometheus_client import CollectorRegistry

    registry = CollectorRegistry()
    reads = []
    identity = SimpleNamespace(
        mode="simulation",
        observation_timestamp=100,
        coordinator_id="producer",
        observation_id="accepted",
        route_id="route",
        replay_runtime_id=None,
        replay_run_id=None,
        replay_revision=None,
        replay_mission_time=None,
    )
    head = SimpleNamespace(
        status="ready",
        reason=None,
        input_revision=7,
        frame=SimpleNamespace(
            identity=identity,
            last_observation_publication_time=99,
            families=tuple((((), 1.0),) for _ in NAMES),
        ),
    )
    store = SimpleNamespace(
        schema=tuple(SimpleNamespace(name=n) for n in NAMES),
        read=lambda: reads.append(True) or head,
    )

    def forbidden():
        raise AssertionError("Adapter collected registry instead of capturing head")

    registry.collect = forbidden
    metrics = SimpleNamespace(FRAME_STORE=store, REGISTRY=registry)
    main = SimpleNamespace(
        _coordinator=SimpleNamespace(mode="simulation", _last_valid_telemetry=None)
    )
    state = capture(main, metrics)
    assert reads == [True]
    assert state["source"]["acquired_at"] == 100
    assert state["publication"]["input_revision"] == 7
    assert all(f["available"] for f in state["fields"].values())
    head.status = "pending"
    assert not any(f["available"] for f in capture(main, metrics)["fields"].values())


def test_legacy_state_is_explicit_and_standard_counters_are_read_only():
    from prometheus_client import CollectorRegistry, Counter, Gauge

    registry = CollectorRegistry()
    for name in NAMES:
        Gauge(name, "Test", registry=registry).set(1)
    counter = Counter("accepted", "Test", registry=registry)
    counter.inc(3)
    telemetry = SimpleNamespace(
        timestamp=SimpleNamespace(timestamp=lambda: 100), metric_source="simulated"
    )
    main = SimpleNamespace(
        _coordinator=SimpleNamespace(mode="simulation", _last_valid_telemetry=telemetry)
    )
    result = capture(main, SimpleNamespace(REGISTRY=registry))
    assert result["publication"]["state"] == "legacy-untracked"
    assert result["source"]["acquired_at"] == 100
    assert registry.get_sample_value("accepted_total") == 3


def test_strict_and_availability_cohorts_cannot_be_compared():
    metadata = {
        "availability_contract": "perf390-availability-v2",
        "harness_files_sha256": {"validator": "abc"},
    }
    run = summarize(metadata, [])
    strict = copy.deepcopy(run)
    strict["metadata"].pop("availability_contract")
    with pytest.raises(ValueError, match="contract"):
        compare(strict, run)
    changed = copy.deepcopy(run)
    changed["metadata"]["harness_files_sha256"] = {"validator": "changed"}
    with pytest.raises(ValueError, match="sources"):
        compare(changed, run)


def test_comparison_requires_recorded_harness_source_and_contract():
    run = {"metadata": {"availability_contract": "perf390-availability-v2"}}
    with pytest.raises(ValueError, match="sources"):
        compare(run, run)


@pytest.mark.parametrize("mutation", ["modified", "untracked"])
def test_uncommitted_harness_source_cannot_claim_a_commit_sha(tmp_path, mutation):
    from acceptance.performance_availability.identity import fingerprints

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=10)
    (tmp_path / "validator.mjs").write_text("original")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, timeout=10)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Fixture",
        ],
        cwd=tmp_path,
        check=True,
        timeout=10,
    )
    (
        tmp_path / ("validator.mjs" if mutation == "modified" else "extra.mjs")
    ).write_text("different")
    with pytest.raises(ValueError, match="Uncommitted harness"):
        fingerprints(tmp_path, [tmp_path])
