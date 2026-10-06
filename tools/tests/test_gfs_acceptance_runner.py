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
