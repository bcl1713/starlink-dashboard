"""A foundation PASS requires every production-path and cleanup proof."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "gfs_acceptance", ROOT / "tools/acceptance/gfs-weather/runner.py"
)


def runner():
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    return module


@pytest.mark.parametrize("dirty,head", [(True, "a" * 40), (False, "b" * 40)])
def test_dirty_or_wrong_sha_prevents_allocation(tmp_path, dirty, head):
    browser = tmp_path / "chrome"
    browser.write_bytes(b"provisioned")
    browser.chmod(0o755)
    with pytest.raises(ValueError, match="committed HEAD"):
        runner().preflight("a" * 40, browser, head, dirty)


def test_missing_browser_prevents_allocation(tmp_path):
    with pytest.raises(ValueError, match="provisioned browser"):
        runner().preflight("a" * 40, tmp_path / "missing", "a" * 40, False)


@pytest.mark.parametrize(
    "missing",
    ["disable_ack", "successful_decode", "metrics", "cleanup", "version_mismatch"],
)
def test_missing_ack_dead_decoder_measurements_or_cleanup_prevents_pass(missing):
    module = runner()
    evidence = {key: True for key in module.REQUIRED_PROOFS}
    evidence["metrics"] = {
        "cpu_usec": 1,
        "memory_peak": 1,
        "disk_bytes": 1,
        "network_bytes": 1,
    }
    evidence["cleanup"] = {
        "containers": [],
        "networks": [],
        "volumes": [],
        "processes": [],
        "ports_free": True,
    }
    evidence.pop(missing)
    with pytest.raises(ValueError, match="incomplete foundation"):
        module.require_pass(evidence)


def test_stale_ack_and_surviving_resources_prevent_pass():
    module = runner()
    evidence = {key: True for key in module.REQUIRED_PROOFS}
    evidence["disable_ack"] = False
    with pytest.raises(ValueError):
        module.require_pass(evidence)


def test_backend_verification_installs_scientific_test_requirements():
    import test_verify

    commands = test_verify.load_verify().BACKEND_COMMANDS
    assert any("requirements-gfs.txt" in arg for arg in commands[0][0])


def complete_evidence(module):
    evidence = {key: True for key in module.REQUIRED_PROOFS}
    evidence["metrics"] = {
        key: 1 for key in ("cpu_usec", "memory_peak", "disk_bytes", "network_bytes")
    }
    evidence["cleanup"] = {
        key: [] for key in ("containers", "networks", "volumes", "processes")
    }
    evidence["cleanup"]["ports_free"] = True
    return evidence


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1])
def test_invalid_measurement_prevents_pass(value):
    module = runner()
    evidence = complete_evidence(module)
    evidence["metrics"]["memory_peak"] = value
    with pytest.raises(ValueError, match="measurements"):
        module.require_pass(evidence)


@pytest.mark.parametrize("kind", ["containers", "networks", "volumes", "processes"])
def test_surviving_owned_resource_prevents_pass(kind):
    module = runner()
    evidence = complete_evidence(module)
    evidence["cleanup"][kind] = ["owned-resource"]
    with pytest.raises(ValueError, match="cleanup"):
        module.require_pass(evidence)


def test_complete_evidence_permits_foundation_pass():
    module = runner()
    module.require_pass(complete_evidence(module))


def test_failed_teardown_still_removes_unaffected_temporary_paths(
    tmp_path, monkeypatch
):
    module = runner()
    source = tmp_path / "source"
    source.mkdir()
    owner = module.Runner.__new__(module.Runner)
    owner.source = source
    owner.output = tmp_path
    owner.allocated = True
    owner.compose = []
    owner.proofs = {}
    owner.owned_processes = {}
    calls = []

    def command(argv, **kwargs):
        calls.append(argv)
        raise RuntimeError("Docker control failed")

    owner.command = command
    owner.inventory = lambda: {key: [] for key in ("containers", "networks", "volumes")}
    monkeypatch.setattr(module, "process_table", lambda: {})

    class FreeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bind(self, address):
            pass

        def setsockopt(self, *args):
            pass

    monkeypatch.setattr(module.socket, "socket", FreeSocket)
    with pytest.raises(RuntimeError):
        owner.cleanup()
    assert not source.exists()
    assert any("down" in argv for argv in calls)
    assert (tmp_path / "cleanup.json").exists()


def test_cleanup_command_error_prevents_pass_even_with_empty_inventory():
    module = runner()
    evidence = complete_evidence(module)
    evidence["cleanup"]["errors"] = ["down failed"]
    with pytest.raises(ValueError, match="cleanup"):
        module.require_pass(evidence)


def test_port_check_rejects_live_listener_and_accepts_closed_time_wait():
    import socket

    module = runner()
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        port = server.getsockname()[1]
        server.listen()
        assert not module.ports_available((port,))
        with socket.create_connection(("127.0.0.1", port)) as client:
            accepted, _ = server.accept()
            accepted.close()
            assert client.recv(1) == b""
    assert module.ports_available((port,))


@pytest.mark.parametrize(
    "missing",
    [
        "native_samples",
        "configuration",
        "lifecycle",
        "combined_viewports",
        "browser_metrics",
    ],
)
def test_presentation_missing_native_controls_or_browser_measurements_prevents_pass(
    missing,
):
    module = runner()
    evidence = complete_evidence(module)
    evidence.update(
        {
            key: True
            for key in [
                "native_samples",
                "configuration",
                "lifecycle",
                "combined_viewports",
            ]
        }
    )
    evidence["browser_metrics"] = {
        "encoded_peak": 1,
        "decoded_peak": 1,
        "gpu_peak": 1,
        "slot_peak": 1,
    }
    evidence.pop(missing)
    with pytest.raises(ValueError, match="presentation"):
        module.require_pass(evidence, "presentation")


@pytest.mark.parametrize(
    "metric", ["encoded_peak", "decoded_peak", "gpu_peak", "slot_peak"]
)
def test_presentation_over_budget_prevents_pass(metric):
    module = runner()
    evidence = complete_evidence(module)
    evidence.update(
        {
            key: True
            for key in [
                "native_samples",
                "configuration",
                "lifecycle",
                "combined_viewports",
            ]
        }
    )
    evidence["browser_metrics"] = {
        key: 1 for key in ["encoded_peak", "decoded_peak", "gpu_peak", "slot_peak"]
    }
    evidence["browser_metrics"][metric] = 100 * 1024**2
    with pytest.raises(ValueError, match="presentation"):
        module.require_pass(evidence, "presentation")


def test_browser_source_uses_candidate_definitions_and_requires_identical_lock(
    tmp_path,
):
    module = runner()
    archived = tmp_path / "candidate"
    installed = tmp_path / "installed"
    for root in (archived, installed):
        (root / "tests/e2e").mkdir(parents=True)
        (root / "package-lock.json").write_bytes(b"pinned dependencies")
    (installed / "node_modules").mkdir()
    (archived / "tests/e2e/gfs-weather-production.spec.ts").write_bytes(
        b"candidate test"
    )
    (installed / "tests/e2e/gfs-weather-production.spec.ts").write_bytes(
        b"edited checkout test"
    )
    proof = module.bind_browser_source(archived, installed, "presentation")
    import hashlib

    assert proof["test_sha256"] == hashlib.sha256(b"candidate test").hexdigest()
    assert (archived / "node_modules").resolve() == installed / "node_modules"
    (installed / "package-lock.json").write_bytes(b"different dependency versions")
    with pytest.raises(ValueError, match="candidate lock"):
        module.bind_browser_source(archived, installed, "presentation")
