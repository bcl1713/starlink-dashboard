"""Real detached-listener failure contracts for the canonical backend runner."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "backend_test_runner.py"


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("normal", 0),
        ("failure", 7),
        ("timeout", 124),
        ("term", 143),
        ("interrupt", 130),
    ],
)
def test_cleanup_catches_detached_listener_and_aborts_progression(
    tmp_path, mode, expected
):
    # Removing descendant adoption/cleanup would leave this real listener alive.
    child = tmp_path / "child.py"
    child.write_text(
        "import os,socket,time,signal\n"
        "s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen()\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "open('listener.json','w').write(__import__('json').dumps([os.getpid(),s.getsockname()[1]]))\n"
        "time.sleep(60)\n"
    )
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import subprocess,sys,time,pathlib\n"
        f"subprocess.Popen([sys.executable,{str(child)!r}],start_new_session=True)\n"
        "while not pathlib.Path('listener.json').exists(): time.sleep(.01)\n"
        + (
            "time.sleep(60)\n"
            if mode in {"timeout", "term", "interrupt"}
            else f"sys.exit({expected})\n"
        )
    )
    harness = tmp_path / "harness.py"
    harness.write_text(
        "import sys\n"
        f"sys.path.insert(0,{str(RUNNER.parent)!r})\n"
        "from backend_test_runner import OwnedRunner\n"
        f"with OwnedRunner({str(tmp_path / 'private')!r},{str(tmp_path / 'evidence')!r},grace=.2) as runner:\n"
        f"    runner.run([sys.executable,{str(driver)!r}],cwd={str(tmp_path)!r},label='first',limit=1)\n"
        f"    runner.run([sys.executable,'-c',\"open('should-not-exist','w').write('bad')\"],cwd={str(tmp_path)!r},label='second',limit=1)\n"
    )
    try:
        if mode in {"term", "interrupt"}:
            proc = subprocess.Popen(
                [sys.executable, str(harness)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 5
                while not (tmp_path / "listener.json").exists():
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
                os.kill(proc.pid, signal.SIGTERM if mode == "term" else signal.SIGINT)
                stdout, stderr = proc.communicate(timeout=10)
                result = subprocess.CompletedProcess(
                    proc.args, proc.returncode, stdout, stderr
                )
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        else:
            result = subprocess.run(
                [sys.executable, str(harness)],
                timeout=15,
                capture_output=True,
                text=True,
                check=False,
            )
        assert result.returncode == expected, result.stdout + result.stderr
        pid, port = json.loads((tmp_path / "listener.json").read_text())
        assert not Path(f"/proc/{pid}").exists()
        import socket

        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0
        evidence = json.loads((tmp_path / "evidence" / "ownership.json").read_text())
        assert evidence["cleanup"]["survivors"] == []
        assert evidence["cleanup"]["listeners"] == []
        assert evidence["runner"]["pid"] > 0
        assert evidence["commands"][0]["exit_code"] == expected
        assert evidence["commands"][0]["subprocess_returncode"] == (
            expected if mode in {"normal", "failure"} else -signal.SIGTERM
        )
        assert any(item["pid"] == pid for item in evidence["owned"])
        assert not (tmp_path / "private").exists()
        assert (tmp_path / "should-not-exist").exists() == (mode == "normal")
    finally:
        # Test-only fallback for a broken implementation; never kill by name/group.
        marker = tmp_path / "listener.json"
        if marker.exists():
            pid, _ = json.loads(marker.read_text())
            if Path(f"/proc/{pid}/cmdline").exists():
                command = Path(f"/proc/{pid}/cmdline").read_bytes()
                if str(child).encode() in command:
                    os.kill(pid, signal.SIGKILL)


def _identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start": fields[19], "state": fields[0]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def _cleanup_test_identities(tmp_path, records):
    """Fallback for red runs: signal/reap only recorded PID/start identities."""
    import shutil

    def survivors():
        result = []
        for record in records:
            current = _identity(record["pid"])
            if current is not None and current["start"] == record["start"]:
                result.append(current)
        return result

    for sig, grace in ((signal.SIGTERM, 0.2), (signal.SIGKILL, 1)):
        deadline = time.monotonic() + grace
        while True:
            for current in survivors():
                if current["state"] != "Z":
                    try:
                        os.kill(current["pid"], sig)
                    except ProcessLookupError:
                        pass
                try:
                    os.waitpid(current["pid"], os.WNOHANG)
                except ChildProcessError:
                    pass
            if not survivors() or time.monotonic() >= deadline:
                break
            time.sleep(0.01)
    remaining = survivors()
    removed = []
    private = tmp_path / "private"
    if not remaining and private.exists():
        shutil.rmtree(private)
        removed.append(str(private))
    (tmp_path / "test-cleanup.json").write_text(
        json.dumps(
            {
                "owned": records,
                "remaining": remaining,
                "removed_private_paths": removed,
            },
            indent=2,
        )
    )
    assert not remaining


@pytest.mark.parametrize("persistent,expected", [(False, 0), (True, 1)])
def test_fd_denial_resampling_preserves_status_and_cleanup(
    tmp_path, persistent, expected
):
    # The old immediate-recheck branch fails transient faults; blanket suppression
    # would incorrectly pass persistent faults. Both exercise real owned sockets.
    import ctypes
    import socket

    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    child = tmp_path / "fd-child.py"
    child.write_text(
        "import json,os,pathlib,signal,socket,time\n"
        "s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen()\n"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        "fields=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()\n"
        "marker=pathlib.Path('fd-listener.json'); temp=marker.with_suffix('.tmp')\n"
        "temp.write_text(json.dumps({'pid':os.getpid(),'start':fields[19],'port':s.getsockname()[1]})); temp.replace(marker)\n"
        "time.sleep(60)\n"
    )
    driver = tmp_path / "fd-driver.py"
    driver.write_text(
        "import json,os,pathlib,subprocess,sys,time\n"
        "pathlib.Path('child-intent.json').write_text(json.dumps({'command':[sys.executable,'fd-child.py'],'pid':None}))\n"
        f"subprocess.Popen([sys.executable,{str(child)!r}],start_new_session=True)\n"
        "while not pathlib.Path('fd-listener.json').exists(): time.sleep(.01)\n"
        "time.sleep(.4)\n"
    )
    harness = tmp_path / "fd-harness.py"
    harness.write_text(
        "import errno,json,pathlib,sys\n"
        f"sys.path.insert(0,{str(RUNNER.parent)!r})\n"
        "from backend_test_runner import OwnedRunner\n"
        "original=pathlib.Path.iterdir; attempts=0\n"
        "def injected(path):\n"
        "    global attempts\n"
        "    marker=pathlib.Path('fd-listener.json')\n"
        "    if path.name=='fd' and path.parent.parent==pathlib.Path('/proc') and marker.exists():\n"
        "        child=json.loads(marker.read_text())\n"
        "        if path.parent.name==str(child['pid']):\n"
        "            attempts+=1\n"
        "            pathlib.Path('fault-count.json').write_text(json.dumps({'attempts':attempts}))\n"
        f"            if {persistent!r} or attempts<=2:\n"
        "                raise PermissionError(errno.EACCES,'injected owned-child FD denial',str(path))\n"
        "    return original(path)\n"
        "pathlib.Path.iterdir=injected\n"
        "try:\n"
        f"    with OwnedRunner({str(tmp_path / 'private')!r},{str(tmp_path / 'evidence')!r},grace=.2) as runner:\n"
        f"        runner.run([sys.executable,{str(driver)!r}],cwd={str(tmp_path)!r},label='first',limit=2)\n"
        f"        runner.run([sys.executable,'-c',\"open('later-command','w').write('ran')\"],cwd={str(tmp_path)!r},label='second',limit=1)\n"
        "finally:\n"
        "    pathlib.Path.iterdir=original\n"
    )
    owner = {
        "runner": _identity(os.getpid()),
        "command": [sys.executable, str(harness)],
        "harness": None,
    }
    (tmp_path / "test-owner.json").write_text(json.dumps(owner, indent=2))
    proc = None
    try:
        proc = subprocess.Popen(
            owner["command"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        owner["harness"] = _identity(proc.pid)
        (tmp_path / "test-owner.json").write_text(json.dumps(owner, indent=2))
        stdout, stderr = proc.communicate(timeout=15)
        assert proc.returncode == expected, stdout + stderr
        listener = json.loads((tmp_path / "fd-listener.json").read_text())
        assert _identity(listener["pid"]) is None
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", listener["port"])) != 0
        evidence = json.loads((tmp_path / "evidence/ownership.json").read_text())
        assert evidence["cleanup"]["survivors"] == []
        assert evidence["cleanup"]["listeners"] == []
        assert evidence["commands"][0]["exit_code"] == expected
        assert evidence["commands"][0]["elapsed_seconds"] > 0
        assert evidence["fd_observations"]
        assert evidence["fd_observations"][0]["pid"] == listener["pid"]
        assert evidence["fd_observations"][0]["start"] == listener["start"]
        if persistent:
            assert (
                "injected owned-child FD denial"
                in evidence["commands"][0]["harness_error"]
            )
            assert evidence["fd_observations"][0]["resolution"] == "persistent"
            assert evidence["commands"][0]["subprocess_returncode"] == -signal.SIGTERM
        else:
            assert evidence["commands"][0]["harness_error"] is None
            assert evidence["fd_observations"][0]["resolution"] == "readable"
        assert json.loads((tmp_path / "fault-count.json").read_text())["attempts"] >= 3
        assert (tmp_path / "later-command").exists() == (not persistent)
        assert not (tmp_path / "private").exists()
    finally:
        records = []
        if owner["harness"] is not None:
            records.append(owner["harness"])
        path = tmp_path / "evidence/ownership.json"
        if path.exists():
            records += json.loads(path.read_text())["owned"]
        marker = tmp_path / "fd-listener.json"
        if marker.exists():
            records.append(json.loads(marker.read_text()))
        try:
            _cleanup_test_identities(tmp_path, records)
            if proc is not None:
                proc.wait(timeout=2)
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
        finally:
            assert libc.prctl(36, previous.value, 0, 0, 0) == 0


@pytest.mark.parametrize("exit_code", [0, 7])
def test_reported_backend_boundary_sets_private_environment_and_cleans_detached_child(
    tmp_path, monkeypatch, exit_code
):
    import backend_test_runner

    repo = tmp_path / "checkout"
    repo.mkdir()
    report = tmp_path / "evidence/report.json"
    private = tmp_path / "private"
    child = tmp_path / "boundary-child.py"
    child.write_text("import time\ntime.sleep(60)\n")
    driver = tmp_path / "boundary-driver.py"
    driver.write_text(
        "import json,os,pathlib,subprocess,sys,time\n"
        f"child=subprocess.Popen([sys.executable,{str(child)!r}],start_new_session=True)\n"
        f'pathlib.Path({str(tmp_path / "boundary.json")!r}).write_text(json.dumps({{"pid":child.pid,"data":os.environ["STARLINK_TEST_DATA_DIR"],"background":os.environ["STARLINK_DISABLE_BACKGROUND_TASKS"],"cache":os.environ["XDG_CACHE_HOME"]}}))\n'
        "time.sleep(.2)\n"
        f"sys.exit({exit_code})\n"
    )
    command = [([sys.executable, str(driver)], repo)]
    if exit_code:
        with pytest.raises(SystemExit) as error:
            backend_test_runner.run_backend(
                repo, command, report=report, run_root=private
            )
        assert error.value.code == exit_code
    else:
        backend_test_runner.run_backend(repo, command, report=report, run_root=private)
    marker = json.loads((tmp_path / "boundary.json").read_text())
    assert marker["data"] == str(private / "bootstrap")
    assert marker["cache"] == str(private / "cache")
    assert marker["background"] == "1"
    assert not Path(f'/proc/{marker["pid"]}').exists()
    ownership = json.loads((report.parent / "ownership.json").read_text())
    assert ownership["cleanup"] == {"survivors": [], "listeners": []}
    assert ownership["private_paths_removed"] is True
    assert not private.exists()
    assert not (repo / ".backend-ci-active").exists()


def test_reported_backend_rejects_shared_checkout_and_inherited_overrides(
    tmp_path, monkeypatch
):
    import backend_test_runner

    repo = tmp_path / "checkout"
    repo.mkdir()
    lock = repo / ".backend-ci-active"
    lock.write_text("another owned run")
    with pytest.raises(FileExistsError):
        backend_test_runner.run_backend(
            repo,
            [],
            report=tmp_path / "evidence/report.json",
            run_root=tmp_path / "private",
        )
    assert not (tmp_path / "private").exists()
    assert lock.read_text() == "another owned run"
    lock.unlink()
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k omit")
    with pytest.raises(ValueError, match="PYTEST_ADDOPTS"):
        backend_test_runner.run_backend(
            repo,
            [],
            report=tmp_path / "evidence/report.json",
            run_root=tmp_path / "private",
        )
    assert not lock.exists()


def test_actual_wrapper_term_cleans_resistant_detached_listener_before_outer_kill(
    tmp_path,
):
    import socket

    repo = tmp_path / "checkout"
    repo.mkdir()
    child = tmp_path / "term-boundary-child.py"
    child.write_text(
        "import json,os,pathlib,signal,socket,time\n"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        's=socket.socket();s.bind(("127.0.0.1",0));s.listen()\n'
        'fields=pathlib.Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()\n'
        f'pathlib.Path({str(tmp_path/"listener.json")!r}).write_text(json.dumps({{"pid":os.getpid(),"start":fields[19],"port":s.getsockname()[1]}}))\n'
        "time.sleep(60)\n"
    )
    driver = tmp_path / "term-boundary-driver.py"
    driver.write_text(
        "import pathlib,subprocess,sys,time\n"
        f"subprocess.Popen([sys.executable,{str(child)!r}],start_new_session=True)\n"
        f'while not pathlib.Path({str(tmp_path/"listener.json")!r}).exists(): time.sleep(.01)\n'
        "time.sleep(60)\n"
    )
    harness = tmp_path / "term-boundary-harness.py"
    harness.write_text(
        "import pathlib,sys\n"
        f"sys.path.insert(0,{str(RUNNER.parent)!r})\n"
        "from backend_test_runner import run_backend\n"
        f'run_backend(pathlib.Path({str(repo)!r}),[([sys.executable,{str(driver)!r}],pathlib.Path({str(repo)!r}))],report=pathlib.Path({str(tmp_path/"evidence/report.json")!r}),run_root=pathlib.Path({str(tmp_path/"private")!r}))\n'
    )
    owner = {
        "command": ["timeout", "--kill-after=10s", "1s", sys.executable, str(harness)],
        "runner": _identity(os.getpid()),
    }
    (tmp_path / "wrapper-test-owner.json").write_text(json.dumps(owner))
    started = time.monotonic()
    records = []
    try:
        result = subprocess.run(
            owner["command"], capture_output=True, text=True, timeout=15, check=False
        )
        assert result.returncode == 124, result.stdout + result.stderr
        assert time.monotonic() - started < 10
        listener = json.loads((tmp_path / "listener.json").read_text())
        records.append(listener)
        assert _identity(listener["pid"]) is None
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", listener["port"])) != 0
        evidence = json.loads((tmp_path / "evidence/ownership.json").read_text())
        records += evidence["owned"]
        assert evidence["cleanup"] == {"survivors": [], "listeners": []}
        assert evidence["commands"][0]["exit_code"] == 143
        assert evidence["private_paths_removed"] is True
        assert not (tmp_path / "private").exists()
        assert not (repo / ".backend-ci-active").exists()
    finally:
        owner_path = tmp_path / "evidence/ownership.json"
        if owner_path.exists():
            records += json.loads(owner_path.read_text())["owned"]
        _cleanup_test_identities(tmp_path, records)
