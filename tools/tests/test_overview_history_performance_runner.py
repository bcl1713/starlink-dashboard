"""Task runner rejects unsafe builds and preserves provenance on failures."""

import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

RUNNER = Path(__file__).parents[1] / "acceptance/overview-history/run.sh"


@pytest.fixture
def checkout(tmp_path):
    runner = tmp_path / "tools/acceptance/overview-history/run.sh"
    runner.parent.mkdir(parents=True)
    shutil.copyfile(RUNNER, runner)
    (tmp_path / "input.txt").write_text("confirmed")
    for args in (
        ["init", "-q"],
        ["add", "."],
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "candidate",
        ],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    return tmp_path, runner


def invoke(checkout, env=None, *args):
    root, runner = checkout
    return subprocess.run(
        ["bash", str(runner), *(args or ("--check",))],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env or os.environ.copy(),
    )


def test_refuses_dirty_tracked_build(checkout):
    (checkout[0] / "input.txt").write_text("draft")
    result = invoke(checkout)
    assert result.returncode != 0
    assert "clean tracked worktree" in result.stderr


@pytest.mark.parametrize("port", [15224, 18224, 19224])
def test_refuses_occupied_loopback_port(checkout, port):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen()
        result = invoke(checkout)
    assert result.returncode != 0
    assert "occupied" in result.stderr


def test_refuses_existing_project_before_build(checkout, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    docker = fake / "docker"
    docker.write_text('#!/bin/sh\nif [ "$1" = ps ]; then echo existing-task; fi\n')
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"}
    result = invoke(checkout, env)
    assert result.returncode != 0
    assert "Existing starlink-224-history" in result.stderr


def test_build_failure_keeps_candidate_provenance(checkout, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    docker = fake / "docker"
    docker.write_text(
        '#!/bin/sh\nfor arg in "$@"; do [ "$arg" = build ] && exit 17; done\nexit 0\n'
    )
    docker.chmod(0o755)
    output = tmp_path / "evidence"
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "OVERVIEW_PROFILE_OUTPUT": str(output),
    }
    result = invoke(
        checkout, env, "--phase", "incremental", "--cadence", "1", "--smoke"
    )
    assert result.returncode == 17, result.stderr
    assert (output / "candidate-sha.txt").exists()
    assert (output / "build.log").exists()


def test_script_separates_browser_and_build_evidence():
    source = RUNNER.read_text()
    assert '/browser"' in source
    assert "trap cleanup EXIT" in source
    assert "starlink-224-history" in source
    assert "--volumes" in source
    assert "git archive" in source


def test_prometheus_loads_the_imported_tsdb_path():
    source = (RUNNER.parent / "compose.yml").read_text()
    assert "--storage.tsdb.path=/prometheus" in source


def test_termination_retains_evidence_and_cleans_owned_project(checkout, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    output = tmp_path / "evidence"
    docker = fake / "docker"
    docker.write_text("""#!/usr/bin/env python3
import os, sys, time
from pathlib import Path
args = sys.argv[1:]
if args[0] in ('ps', 'volume'):
    sys.exit(0)
output = Path(os.environ['OVERVIEW_PROFILE_OUTPUT'])
output.mkdir(exist_ok=True)
with (output / 'docker-calls.txt').open('a') as log:
    log.write(' '.join(args) + '\\n')
if 'up' in args:
    (output / 'up-started').write_text('owned')
    time.sleep(300)
""")
    docker.chmod(0o755)
    python = fake / "profile-python"
    python.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
if '--output' in sys.argv:
    Path(sys.argv[sys.argv.index('--output') + 1]).write_text('# EOF\\n')
""")
    python.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "OVERVIEW_PROFILE_OUTPUT": str(output),
        "OVERVIEW_PROFILE_PYTHON": str(python),
    }
    process = subprocess.Popen(
        ["bash", str(checkout[1]), "--smoke"],
        cwd=checkout[0],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        for _ in range(100):
            if (output / "up-started").exists() or process.poll() is not None:
                break
            time.sleep(0.05)
        assert (output / "up-started").exists()
        os.killpg(process.pid, signal.SIGTERM)
        _, error = process.communicate(timeout=5)
        assert process.returncode == 143, error.decode()
        assert (output / "cleanup.log").exists()
        assert "down --volumes" in (output / "docker-calls.txt").read_text()
        assert (output / "candidate-sha.txt").exists()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def test_refuses_nonempty_evidence_instead_of_mixing_phases(checkout, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    docker = fake / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o755)
    output = tmp_path / "evidence"
    output.mkdir()
    (output / "samples.jsonl").write_text("existing")
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "OVERVIEW_PROFILE_OUTPUT": str(output),
    }
    result = invoke(checkout, env, "--smoke")
    assert result.returncode != 0
    assert "nonempty evidence" in result.stderr
    assert (output / "samples.jsonl").read_text() == "existing"
