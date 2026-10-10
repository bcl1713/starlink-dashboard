"""Run the actual ownership boundary against disposable process trees."""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/acceptance/itinerary-planning/runner.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("itinerary_runner", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mode", ["normal", "failure", "deadline", "term"])
def test_owned_process_tree_is_removed_on_every_exit(tmp_path, mode):
    # A real descendant outlives its parent unless the runner owns the full group.
    launcher = tmp_path / "launch.py"
    launcher.write_text("""import subprocess,sys,time
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])
print(child.pid,flush=True)
mode=sys.argv[1]
if mode=='normal': sys.exit(0)
if mode=='failure': sys.exit(7)
time.sleep(120)
""")
    harness = tmp_path / "harness.py"
    harness.write_text(f"""import importlib.util, pathlib, signal
spec=importlib.util.spec_from_file_location('runner',{str(RUNNER)!r})
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
o=m.Owner(pathlib.Path({str(tmp_path)!r}),'a'*40)
signal.signal(signal.SIGTERM,o.signal)
try:
 o.execute(['{sys.executable}',{str(launcher)!r},{mode!r}],timeout={0.4 if mode == 'deadline' else 10})
finally:
 o.close_processes()
""")
    process = subprocess.Popen([sys.executable, str(harness)], start_new_session=True)
    try:
        deadline = time.monotonic() + 4
        ownership = tmp_path / "ownership.json"
        while time.monotonic() < deadline:
            if ownership.exists():
                data = json.loads(ownership.read_text())
                if (
                    data["commands"]
                    and data["commands"][0].get("pid")
                    and Path(data["commands"][0]["log"]).stat().st_size
                ):
                    break
            if process.poll() is not None:
                break
            time.sleep(0.02)
        if mode == "term" and process.poll() is None:
            process.send_signal(signal.SIGTERM)
        process.wait(timeout=12)
        assert ownership.exists(), "runner must persist ownership before launch"
        record = json.loads(ownership.read_text())
        assert record["commands"][0]["reaped"] is True
        assert record["cleanup"]["processes_gone"] is True
        pgid = record["commands"][0]["pgid"]
        with pytest.raises(ProcessLookupError):
            os.killpg(pgid, 0)
        assert (process.returncode == 0) == (mode == "normal")
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)


def test_preflight_refuses_existing_project_without_cleanup(monkeypatch, tmp_path):
    module = load_runner()
    owner = module.Owner(tmp_path, "a" * 40)
    calls = []

    def command(argv, **kwargs):
        calls.append(argv)
        return "foreign-network" if "network" in argv else ""

    monkeypatch.setattr(owner, "execute", command)
    with pytest.raises(RuntimeError, match="Existing"):
        module.preflight(owner)
    assert not any("down" in command for command in calls)


def test_topology_has_no_shims_and_uses_private_volumes():
    import yaml

    config = yaml.safe_load((RUNNER.parent / "compose.yml").read_text())
    backend = config["services"]["starlink-location"]
    assert "command" not in backend
    assert all(":/acceptance" not in volume for volume in backend["volumes"])
    assert config["services"]["mission-planner"]["ports"] == ["127.0.0.1:15322:80"]
    assert all(
        not details or not details.get("external")
        for details in config["volumes"].values()
    )


def test_synthetic_seed_is_a_real_three_leg_five_window_pdf(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "backend/starlink-location"))
    from app.mission.planning.extract import extract_itinerary

    spec = importlib.util.spec_from_file_location(
        "itinerary_seed", RUNNER.parent / "seed.py"
    )
    assert spec and spec.loader
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    result = extract_itinerary(seed.pdf(1))
    assert result.parsed_values is not None
    assert len(result.parsed_values.expected_legs) == 3
    assert sum(len(leg.ar_rows) for leg in result.parsed_values.expected_legs) == 5
    assert result.parsed_values.expected_legs[1].ar_rows == []
