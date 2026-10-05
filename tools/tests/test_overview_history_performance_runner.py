"""Task runner rejects unsafe builds and preserves provenance on failures."""

import json
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
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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


def test_finished_tcp_connection_is_not_an_occupied_listener(checkout, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    docker = fake / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"}
    # A server actively closing its last connection leaves TIME_WAIT, even
    # though the listener and process are gone. Real live listeners must still
    # be rejected by the separate occupied-port controls above.
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 18224))
        listener.listen()
        with socket.create_connection(("127.0.0.1", 18224)) as client:
            peer, _ = listener.accept()
            with peer:
                peer.shutdown(socket.SHUT_RDWR)
            assert client.recv(1) == b""
    result = invoke(checkout, env)
    assert result.returncode == 0, result.stderr


def test_cleanup_accepts_closed_connection_but_retains_inventory(checkout, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    docker = fake / "docker"
    docker.write_text("""#!/usr/bin/env python3
import socket, sys
if 'down' in sys.argv:
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 18224))
        listener.listen()
        with socket.create_connection(('127.0.0.1', 18224)) as client:
            peer, _ = listener.accept()
            with peer:
                peer.shutdown(socket.SHUT_RDWR)
            assert client.recv(1) == b''
""")
    docker.chmod(0o755)
    curl = fake / "curl"
    curl.write_text("#!/bin/sh\nprintf '{}\\n'\n")
    curl.chmod(0o755)
    profile_python = fake / "profile-python"
    profile_python.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
if '--output' in sys.argv:
    Path(sys.argv[sys.argv.index('--output') + 1]).write_text('# EOF\\n')
""")
    profile_python.chmod(0o755)
    output = tmp_path / "evidence"
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "OVERVIEW_PROFILE_OUTPUT": str(output),
        "OVERVIEW_PROFILE_PYTHON": str(profile_python),
    }
    result = invoke(checkout, env, "--smoke")
    assert (output / "cleanup.log").exists(), result.stderr
    assert result.returncode == 0, (output / "cleanup.log").read_text()
    assert "no live listener" in (output / "cleanup.log").read_text()


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


def test_trace_export_does_not_require_rootless_bind_remounts():
    source = RUNNER.read_text()
    assert 'docker exec "$backend" cat /data/overview-history-queries.jsonl' in source
    assert 'docker exec "$backend" cat /data/overview-history-reads.jsonl' in source


@pytest.mark.parametrize("operation", ["ps", "volume"])
def test_preflight_inventory_errors_refuse_startup(checkout, tmp_path, operation):
    fake = tmp_path / "bin"
    fake.mkdir()
    docker = fake / "docker"
    docker.write_text(f'#!/bin/sh\nif [ "$1" = {operation} ]; then exit 17; fi\n')
    docker.chmod(0o755)
    result = invoke(checkout, {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"})
    assert result.returncode != 0, "Failed Docker inventory was treated as empty"


@pytest.mark.parametrize("failure", ["backend_lookup", "ps", "volume"])
def test_cleanup_audit_errors_fail_closed_and_still_attempt_down(
    checkout, tmp_path, failure
):
    fake = tmp_path / "bin"
    fake.mkdir()
    docker = fake / "docker"
    docker.write_text("""#!/usr/bin/env python3
import os,sys
from pathlib import Path
args=sys.argv[1:]
out=Path(os.environ['OVERVIEW_PROFILE_OUTPUT'])
if out.exists():
    with (out/'docker-calls.txt').open('a') as log:log.write(' '.join(args)+'\\n')
fail=os.environ['FAILURE']
if args[0]=='compose' and 'ps' in args and fail=='backend_lookup':sys.exit(17)
if args[0] in ('ps','volume') and (out/'down-attempted').exists() and args[0]==fail:sys.exit(17)
if 'down' in args:(out/'down-attempted').touch()
""")
    docker.chmod(0o755)
    curl = fake / "curl"
    curl.write_text("#!/bin/sh\nprintf '{}\\n'\n")
    curl.chmod(0o755)
    python = fake / "profile-python"
    python.write_text("""#!/usr/bin/env python3
import sys,json
from pathlib import Path
args=sys.argv
if '--output' in args:Path(args[args.index('--output')+1]).write_text('# EOF\\n')
if '--artifacts' in args:
    out=Path(args[args.index('--artifacts')+1]);out.mkdir(parents=True)
    (out/'metadata.json').write_text(json.dumps({'cleanup':'pending'}))
    (out/'browser-cleanup.json').write_text(json.dumps({'status':'passed'}))
""")
    python.chmod(0o755)
    output = tmp_path / "evidence"
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "OVERVIEW_PROFILE_OUTPUT": str(output),
        "OVERVIEW_PROFILE_PYTHON": str(python),
        "FAILURE": failure,
    }
    result = invoke(checkout, env, "--duration", "60")
    assert (output / "down-attempted").exists(), result.stderr
    assert result.returncode != 0, "Failed cleanup audit qualified as empty inventory"

    assert (
        json.loads((output / "browser/metadata.json").read_text())["cleanup"]
        == "failed"
    )
