"""Acceptance rejects ambiguous candidates and always reaps its own resources."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools/acceptance/operator-journal/run.py"


def implementation():
    assert ENTRY.exists(), "Operator production acceptance runner is missing"
    sys.path.insert(0, str(ENTRY.parent))
    spec = importlib.util.spec_from_file_location("operator_acceptance", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repository(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True, timeout=10)
    (path / "tracked").write_text("candidate")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, timeout=10)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Acceptance",
            "-c",
            "user.email=acceptance@example.invalid",
            "commit",
            "-qm",
            "candidate",
        ],
        check=True,
        timeout=10,
    )
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True, timeout=10
    ).strip()


@pytest.mark.parametrize("damage", ["dirty", "untracked", "mismatch", "short", None])
def test_candidate_requires_clean_exact_head(tmp_path, damage):
    value = implementation()
    sha = repository(tmp_path)
    if damage == "dirty":
        (tmp_path / "tracked").write_text("changed")
    elif damage == "untracked":
        (tmp_path / "extra").touch()
    elif damage == "mismatch":
        sha = "0" * 40
    elif damage == "short":
        sha = sha[:12]
    if damage:
        with pytest.raises(ValueError, match="clean committed full HEAD"):
            value.validate_candidate(tmp_path, sha)
    else:
        value.validate_candidate(tmp_path, sha)


@pytest.mark.parametrize("damage", ["revision", "image", "missing", None])
def test_image_identity(tmp_path, damage):
    value = implementation()
    identity = {
        "Id": "sha256:" + "a" * 64,
        "Config": {"Labels": {"org.opencontainers.image.revision": "b" * 40}},
    }
    if damage == "revision":
        identity["Config"]["Labels"]["org.opencontainers.image.revision"] = "c" * 40
    elif damage == "image":
        identity["Id"] = ""
    elif damage == "missing":
        identity["Config"]["Labels"] = {}
    if damage:
        with pytest.raises(ValueError, match="image identity"):
            value.validate_image(identity, "b" * 40)
    else:
        assert value.validate_image(identity, "b" * 40)["id"] == identity["Id"]


def test_timeout_kills_and_reaps_recorded_child(tmp_path):
    owner = implementation().Owner("starlink-operator-timeout-test", tmp_path)
    with pytest.raises(TimeoutError):
        owner.execute(
            [sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.1
        )
    entry = json.loads((tmp_path / "ownership.json").read_text())["commands"][0]
    assert entry["reaped"] and not entry["groupRemaining"]
    with pytest.raises(ProcessLookupError):
        os.kill(entry["pid"], 0)


def test_early_failure_has_summary_and_scoped_volume_teardown(tmp_path, monkeypatch):
    value = implementation()
    sha = repository(tmp_path / "repo")
    commands = []

    def execute(self, command, **_kwargs):
        commands.append(command)
        return ""

    def fail(_owner, _candidate):
        raise RuntimeError("early build failure")

    monkeypatch.setattr(value, "ROOT", tmp_path / "repo")
    monkeypatch.setattr(value.Owner, "execute", execute)
    monkeypatch.setattr(value, "build_candidate", fail)
    with pytest.raises(RuntimeError, match="early build"):
        value.run(sha, "starlink-operator-early-test", tmp_path / "evidence")
    report = json.loads((tmp_path / "evidence/summary.json").read_text())
    assert not report["checksPassed"]
    assert report["cleanup"]["composeRemoved"]
    down = next(command for command in commands if "down" in command)
    assert down[down.index("-p") + 1] == "starlink-operator-early-test"
    assert "--volumes" in down
    assert all("prune" not in command for command in commands)
    queries = [command for command in commands if "--filter" in command]
    assert len(queries) >= 3
    assert all(
        "label=com.docker.compose.project=starlink-operator-early-test" in c
        for c in queries
        if any(arg.startswith("label=") for arg in c)
    )


def test_existing_evidence_is_not_overwritten(tmp_path, monkeypatch):
    value = implementation()
    sha = repository(tmp_path / "repo")
    monkeypatch.setattr(value, "ROOT", tmp_path / "repo")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "other-owner").write_text("keep")
    with pytest.raises(ValueError, match="new evidence"):
        value.run(sha, "starlink-operator-existing-test", evidence)
    assert (evidence / "other-owner").read_text() == "keep"


def test_loopback_relay_preserves_bytes_and_reaps_transport():
    implementation()
    path = ENTRY.with_name("relay.py")
    assert path.exists(), "Offline production loopback relay is missing"
    spec = importlib.util.spec_from_file_location("operator_relay", path)
    relay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(relay)
    server = relay.Server(
        ("127.0.0.1", 0),
        [sys.executable, "-u", "-c", "import os; os.write(1,os.read(0,4096))"],
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with socket.create_connection(server.server_address, timeout=3) as client:
            client.sendall(b"unaltered production HTTP bytes\r\n")
            assert client.recv(4096) == b"unaltered production HTTP bytes\r\n"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert not thread.is_alive()
    assert not server.children


def test_failed_browser_still_exercises_independent_storage_checks(tmp_path):
    module = implementation()
    assert hasattr(module, "run_checks"), "Independent acceptance checks are missing"

    def broken_browser():
        raise RuntimeError("browser failed")

    def storage():
        (tmp_path / "storage-tested").touch()
        return {"full": True}

    with pytest.raises(RuntimeError, match="browser"):
        module.run_checks(tmp_path, {"browser": broken_browser, "storage": storage})
    assert (tmp_path / "storage-tested").exists()
    report = json.loads((tmp_path / "qualification.json").read_text())
    assert report["checks"]["storage"]["full"]
    assert report["errors"] == {"browser": "browser failed"}
