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


@pytest.fixture
def main_run(monkeypatch, tmp_path):
    """Drive actual main/Owner orchestration without launching Docker or a server."""
    import io
    import tarfile
    from types import SimpleNamespace

    monkeypatch.syspath_prepend(str(ROOT))
    from tools.acceptance import compose

    module = load_runner()
    output = tmp_path / "evidence"
    sha = "a" * 40
    state = {"calls": [], "builds": 0, "started": False, "down": False}
    monkeypatch.setenv("ITINERARY_EVIDENCE_DIR", str(output))
    monkeypatch.setattr(sys, "argv", [str(RUNNER)])
    monkeypatch.setattr(
        module,
        "CLAIM_NAME",
        f"itinerary-test-{os.getpid()}-{tmp_path.name}",
        raising=False,
    )
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda argv, **kw: sha if argv[1] == "rev-parse" else "",
    )
    monkeypatch.setattr(
        compose, "parse_buildkit_log", lambda *args: [SimpleNamespace(complete=True)]
    )
    monkeypatch.setattr(module, "verify_clone_snapshot", lambda owner, source: None)
    original_remove = module.shutil.rmtree
    original_close = module.Owner.close_processes
    original_unlink = module.Path.unlink

    def run(fault):
        def port():
            state["calls"].append("port")
            if fault == "port" and state["down"]:
                raise RuntimeError("owned port still bound")

        monkeypatch.setattr(module, "check_port", port)

        def execute(owner, command, **kwargs):
            assert owner.claim is not None
            assert owner.record["claim"]["state"] == "acquired"
            state["calls"].append(command)
            if command[:2] == ["git", "archive"]:
                archive = Path(
                    next(
                        arg.split("=", 1)[1]
                        for arg in command
                        if arg.startswith("--output=")
                    )
                )
                with tarfile.open(archive, "w") as bundle:
                    content = b"owned source"
                    entry = tarfile.TarInfo("owned.txt")
                    entry.size = len(content)
                    bundle.addfile(entry, io.BytesIO(content))
            elif command[:2] == ["docker", "build"]:
                state["builds"] += 1
            elif command[:3] == ["docker", "image", "inspect"]:
                return json.dumps(
                    {
                        "Id": "exact-image",
                        "Config": {
                            "Labels": {"org.opencontainers.image.revision": sha}
                        },
                    }
                )
            elif command[:2] == ["docker", "compose"]:
                action = command[6]
                if action == "up":
                    state["started"] = True
                    if fault in {"startup", "startup_logs"}:
                        raise RuntimeError("primary startup failure")
                if action == "logs" and fault in {"logs", "startup_logs"}:
                    raise RuntimeError("diagnostic logs failure")
                if action == "down":
                    state["down"] = True
                    if fault == "down":
                        raise RuntimeError("down unavailable")
                if action == "ps":
                    return "owned-container"
            elif command[:2] == ["docker", "inspect"]:
                return "exact-image"
            elif command[0] == "curl":
                return "{}"
            elif command[:2] == ["node", "--version"]:
                return "v22.22.2"
            elif command[0] == "node" and "--provenance-file" in command:
                browser = Path(command[command.index("--browser-root") + 1])
                browser.mkdir()
                (browser / "owned-browser").write_text("owned")
                Path(command[command.index("--provenance-file") + 1]).write_text(
                    json.dumps({"executable": {"path": str(browser / "chrome")}})
                )
            for kind, prefix in module.RESOURCE_COMMANDS.items():
                if (
                    state["down"]
                    and command[: len(prefix)] == prefix
                    and fault == f"audit-{kind}"
                ):
                    raise RuntimeError(f"{kind} audit unavailable")
            if command[:2] == ["docker", "ps"] and state["down"] and fault == "down":
                return "owned-container-remains"
            if (
                command[:3] == ["docker", "network", "ls"]
                and fault == "foreign"
                and state["builds"] == 2
            ):
                return "foreign-network"
            return ""

        close_count = 0

        def close(owner):
            nonlocal close_count
            close_count += 1
            state["calls"].append("process-close")
            if fault == "process-close" and close_count == 1:
                raise RuntimeError("owned child stop failed")
            return original_close(owner)

        def remove(path, *args, **kwargs):
            if (fault == "temp" and Path(path).name == "candidate-source") or (
                fault == "temp-browser" and Path(path).name == "browsers"
            ):
                raise PermissionError(f"owned removal failed: {path}")
            return original_remove(path, *args, **kwargs)

        def unlink(path, *args, **kwargs):
            if fault == "temp-archive" and path.name == "candidate-source.tar":
                raise PermissionError(f"owned archive removal failed: {path}")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(module.Path, "unlink", unlink)
        monkeypatch.setattr(module.Owner, "execute", execute)
        monkeypatch.setattr(module.Owner, "close_processes", close)
        monkeypatch.setattr(module.shutil, "rmtree", remove)
        caught = None
        try:
            module.main()
        except (RuntimeError, OSError) as exc:
            caught = exc
        return caught, json.loads((output / "summary.json").read_text()), output, state

    return run


@pytest.mark.parametrize(
    "fault",
    [
        "normal",
        "startup",
        "logs",
        "startup_logs",
        "process-close",
        "down",
        "audit-containers",
        "audit-networks",
        "audit-volumes",
        "port",
        "temp",
        "temp-browser",
        "temp-archive",
    ],
)
def test_main_attempts_independent_cleanup_after_each_fault(main_run, fault):
    error, summary, output, state = main_run(fault)
    assert state["down"], "every owned startup must attempt down"
    assert state["calls"].count("process-close") >= 2
    down_index = next(
        i
        for i, call in enumerate(state["calls"])
        if isinstance(call, list)
        and call[:2] == ["docker", "compose"]
        and call[6] == "down"
    )
    later = state["calls"][down_index + 1 :]
    assert "port" in later
    for command in (
        ["docker", "ps"],
        ["docker", "network", "ls"],
        ["docker", "volume", "ls"],
    ):
        assert any(
            isinstance(call, list) and call[: len(command)] == command for call in later
        )
    assert (output / "candidate-source.tar").exists() == (fault == "temp-archive")
    assert (output / "browsers").exists() == (fault == "temp-browser")
    assert summary["claim"]["state"] == "released"
    assert (output / "candidate-source").exists() == (fault == "temp")
    assert summary["passed"] == (fault == "normal")
    assert (error is None) == (fault == "normal")
    if fault == "startup_logs":
        assert "primary startup failure" in str(error)
        assert summary["error"] == "primary startup failure"
        assert "diagnostic logs failure" in json.dumps(summary["cleanup_errors"])
    if fault == "down":
        assert (
            summary["cleanup"]["resources"]["containers"] == "owned-container-remains"
        )
    if fault.startswith("audit-"):
        kind = fault.removeprefix("audit-")
        assert summary["cleanup"]["resources"][kind] is None
        assert all(
            value == ""
            for key, value in summary["cleanup"]["resources"].items()
            if key != kind
        )
    if fault == "port":
        assert summary["cleanup"]["port_free"] is False
    if fault == "temp":
        assert (
            str(output / "candidate-source")
            in summary["cleanup"]["temporary_survivors"]
        )


def test_foreign_project_appearing_during_build_is_never_owned_or_torn_down(main_run):
    error, summary, output, state = main_run("foreign")
    assert error is not None
    assert not state["started"] and not state["down"]
    assert not summary["passed"]
    assert not (output / "candidate-source").exists()


def test_process_cleanup_attempts_later_children_after_first_failure(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    module = load_runner()
    owner = module.Owner(tmp_path, "a" * 40)
    children = [
        SimpleNamespace(pid=101, returncode=None),
        SimpleNamespace(pid=102, returncode=0),
    ]
    owner.children = children.copy()
    attempted = []

    def stop(child):
        attempted.append(child.pid)
        if child.pid == 101:
            raise RuntimeError("owned group 101 survives")

    monkeypatch.setattr(owner, "stop", stop)
    with pytest.raises(RuntimeError, match="101"):
        owner.close_processes()
    assert attempted == [101, 102]
    assert owner.children == [children[0]]
    assert owner.record["cleanup"]["processes_gone"] is False


@pytest.mark.parametrize("exit_mode", ["normal", "crash"])
def test_real_claim_contends_before_preflight_and_releases_on_exit(tmp_path, exit_mode):
    claim_name = f"itinerary-claim-{os.getpid()}-{tmp_path.name}"
    holder = tmp_path / "holder.py"
    holder.write_text(f"""import importlib.util,pathlib,sys
spec=importlib.util.spec_from_file_location('runner',{str(RUNNER)!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.CLAIM_NAME={claim_name!r}
o=m.Owner(pathlib.Path({str(tmp_path / 'holder')!r}),'a'*40)
o.acquire_claim()
print('claimed',flush=True)
sys.stdin.readline()
o.release_claim()
""")
    contender = tmp_path / "contender.py"
    mutation = tmp_path / "preflight-called"
    contender.write_text(f"""import importlib.util,pathlib,os,sys
spec=importlib.util.spec_from_file_location('runner',{str(RUNNER)!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.CLAIM_NAME={claim_name!r}
m.subprocess.check_output=lambda argv,**kw: 'a'*40 if argv[1]=='rev-parse' else ''
m.preflight=lambda owner:pathlib.Path({str(mutation)!r}).write_text('preflight')
os.environ['ITINERARY_EVIDENCE_DIR']=sys.argv.pop()
sys.argv=[sys.argv[0],'--check']
m.main()
""")
    process = subprocess.Popen(
        [sys.executable, str(holder)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 4
        owner_path = tmp_path / "holder/ownership.json"
        while time.monotonic() < deadline:
            if (
                owner_path.exists()
                and json.loads(owner_path.read_text()).get("claim", {}).get("state")
                == "acquired"
            ):
                break
            if process.poll() is not None:
                break
            time.sleep(0.02)
        assert process.poll() is None, "holder must acquire the real kernel claim"
        assert json.loads(owner_path.read_text())["claim"]["state"] == "acquired"
        result = subprocess.run(
            [sys.executable, str(contender), str(tmp_path / "denied")],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
        assert result.returncode != 0
        assert not mutation.exists(), "contender must fail before preflight or mutation"
        assert (
            json.loads((tmp_path / "denied/ownership.json").read_text())["claim"][
                "state"
            ]
            == "contended"
        )
        if exit_mode == "crash":
            process.kill()
        else:
            process.communicate("release\n", timeout=5)
        process.wait(timeout=5)
        result = subprocess.run(
            [sys.executable, str(contender), str(tmp_path / "success")],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, result.stderr
        assert mutation.read_text() == "preflight"
        assert (
            json.loads((tmp_path / "success/ownership.json").read_text())["claim"][
                "state"
            ]
            == "released"
        )
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


@pytest.mark.parametrize("fault", [None, "cached", "interval", "context", "writes"])
def test_clone_export_receipt_requires_rebuilt_equivalent_timeline(tmp_path, fault):
    import zipfile
    from types import SimpleNamespace

    module = load_runner()
    expected = {
        "id": "clone",
        "legs": [
            {
                "id": "leg",
                "transports": {"evaluation_context": {"input_identity": "same"}},
            }
        ],
    }
    (tmp_path / "collision-views.json").write_text(
        json.dumps(
            {
                "beforeClone": {"mission": {"id": "original"}},
                "cloneView": {"mission": expected},
            }
        )
    )
    with zipfile.ZipFile(tmp_path / "synthetic-package.zip", "w") as package:
        package.writestr("mission.json", '{"id":"original"}')
    script = tmp_path / "tools/acceptance/itinerary-planning/verify-clone.py"
    script.parent.mkdir(parents=True)
    script.write_text("read_only_proof")
    receipt = {
        "original_mission_id": "original",
        "mission_id": "clone",
        "stored_files_unchanged": fault != "writes",
        "legs": [
            {
                "leg_id": "leg",
                "context": {
                    "input_identity": "changed" if fault == "context" else "same"
                },
                "preparation_origins": [
                    "rebuilt",
                    "cached" if fault == "cached" else "rebuilt",
                ],
                "canonical_evaluations_equal": True,
                "export_intervals_equal": fault != "interval",
            }
        ],
    }
    owner = SimpleNamespace(
        output=tmp_path,
        compose=lambda *args, **kwargs: "CANONICAL_RECEIPT=" + json.dumps(receipt),
    )
    if fault:
        with pytest.raises(AssertionError):
            module.verify_clone_snapshot(owner, tmp_path)
    else:
        module.verify_clone_snapshot(owner, tmp_path)
    assert json.loads((tmp_path / "clone-export-rebuild.json").read_text()) == receipt
