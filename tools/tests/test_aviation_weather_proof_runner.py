"""Fixture routing and runner ownership contract."""

import ast
from pathlib import Path

import pytest
from acceptance.aviation_weather_proof.run_browser import validate_arguments


def test_fixture_mount_only_in_proof_mode():
    source = Path("tools/acceptance/overview-weather/backend_fixture.py").read_text()
    tree = ast.parse(source)
    branches = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If) and "aviation-proof" in ast.unparse(n.test)
    ]
    assert len(branches) == 1
    assert "/api/overview-weather/aviation-proof-assets" in ast.unparse(branches[0])
    assert "StaticFiles" in ast.unparse(branches[0])


def test_invalid_browser_arguments_rejected():
    with pytest.raises(ValueError):
        validate_arguments(["--origin", "https://example.com"])


def test_private_products_are_readable_only_inside_fixture_mount(tmp_path):
    from acceptance.aviation_weather_proof.runner import prepare_fixture_mount

    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    products = parent / "products"
    products.mkdir()
    product = products / "gfs"
    product.mkdir(mode=0o700)
    (product / "descriptor.json").write_text("{}")
    prepare_fixture_mount(products)
    assert product.stat().st_mode & 0o777 == 0o755
    assert parent.stat().st_mode & 0o777 == 0o700


def test_port_cleanup_waits_for_release_and_still_rejects_live_listener():
    import socket
    import threading

    from acceptance.aviation_weather_proof.runner import wait_ports_free

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    try:
        blocked = wait_ports_free([port], seconds=0.02)
        assert blocked["remaining"] == [f"listener:{port}"]
        assert blocked["observations"]
        closer = threading.Timer(0.05, listener.close)
        closer.start()
        try:
            released = wait_ports_free([port], seconds=1)
            assert released["remaining"] == []
        finally:
            closer.join()
    finally:
        listener.close()


def test_entrypoint_uses_persistent_actor_lock_and_retains_it_until_exit(tmp_path):
    import os
    import subprocess
    import textwrap

    actor_cache = tmp_path / "actor-cache"
    lock = actor_cache / "starlink-acceptance" / "scientific-decoder.lock"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    receipt = tmp_path / "receipt"
    python = bin_dir / "python3"
    python.write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        set -euo pipefail
        test "$1" = -m
        test "$2" = acceptance.aviation_weather_proof.runner
        test -f "$PROOF_EXPECTED_LOCK"
        if flock -n "$PROOF_EXPECTED_LOCK" true; then exit 9; fi
        printf 'held' > "$PROOF_LOCK_RECEIPT"
    """))
    python.chmod(0o700)
    env = {
        **os.environ,
        "XDG_CACHE_HOME": str(actor_cache),
        "PATH": f'{bin_dir}:{os.environ["PATH"]}',
        "PROOF_EXPECTED_LOCK": str(lock),
        "PROOF_LOCK_RECEIPT": str(receipt),
    }
    result = subprocess.run(
        [
            "bash",
            "tools/acceptance/aviation_weather_proof/run.sh",
            "0" * 40,
            "/capture",
            "/profile",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert receipt.read_text() == "held"
    assert (
        subprocess.run(
            ["flock", "-n", str(lock), "true"], timeout=5, check=False
        ).returncode
        == 0
    )
    assert lock.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("interrupt", ["deadline", "SIGTERM"])
def test_timeout_cleans_owned_container_and_seals_failure(tmp_path, interrupt):
    import os
    import subprocess
    import sys
    import textwrap

    if os.environ.get("PROOF_LIFECYCLE_DOCKER") != "1":
        pytest.skip("explicit actor-Docker lifecycle regression")
    script = tmp_path / "control.py"
    script.write_text(textwrap.dedent(f"""
        import json, os, signal, subprocess, sys, time
        from pathlib import Path
        from acceptance.aviation_weather_proof.lifecycle import Deadline, enable_subreaper
        from acceptance.aviation_weather_proof.runner import cleanup_owned_runtime, publish_evidence, IMAGE
        from acceptance.platform.evidence import verify_manifest, read_fingerprint_authority
        root=Path(sys.argv[1]); output=root/'evidence'; output.mkdir()
        name='starlink-290-failure-control-'+root.name.lower().replace('_','-')
        owner={{'workers':[name],'children':[]}}
        (output/'runtime-owner.json').write_text(json.dumps(owner))
        enable_subreaper()
        subprocess.run(['docker','create','--name',name,'--label','starlink-290.failure-control=true','--network','none','--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','32','--entrypoint','python',IMAGE,'-c','import time; time.sleep(60)'],check=True,capture_output=True,timeout=10)
        subprocess.run(['docker','start',name],check=True,capture_output=True,timeout=10)
        started=time.monotonic()
        try:
            with Deadline(work_seconds=.1,total_seconds=8,signal_seconds=7) as budget:
                try:
                    if {interrupt!r}=='SIGTERM': os.kill(os.getpid(),signal.SIGTERM)
                    time.sleep(30)
                except (TimeoutError,InterruptedError) as error:
                    (output/'failure.json').write_text(json.dumps({{'error':str(error)}}))
                finally:
                    budget.begin_cleanup()
                    cleanup_owned_runtime(output,owner,budget,compose=None,env=None,ports=[])
                result=publish_evidence(root,output,'0'*40,root/'sealed',budget=budget)
            cleanup=json.loads((output/'cleanup.json').read_text())
            sealed=root/'sealed'/root.name/('0'*40)
            verify_manifest(sealed); read_fingerprint_authority(sealed)
            assert result==1
            assert cleanup['remaining']==[]
            assert subprocess.run(['docker','inspect',name],capture_output=True,timeout=2).returncode!=0
            assert (sealed/'failure.json').exists()
            assert time.monotonic()-started<8
        finally:
            subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=5)
    """))
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=35,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_late_sigterm_during_port_cleanup_retains_sealed_failure(tmp_path):
    import subprocess
    import sys
    import textwrap

    script = tmp_path / "control.py"
    script.write_text(textwrap.dedent("""
        import json,os,signal,socket,sys,threading,time
        from pathlib import Path
        from acceptance.aviation_weather_proof.lifecycle import Deadline
        from acceptance.aviation_weather_proof.runner import cleanup_owned_runtime,publish_evidence
        from acceptance.platform.evidence import verify_manifest,read_fingerprint_authority
        root=Path(sys.argv[1]);output=root/'evidence';output.mkdir()
        # Similar size to the retained native evidence, so sealing is not a tiny placeholder.
        (output/'diagnostic-payload.bin').write_bytes(bytes(32*1024*1024))
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
        port=listener.getsockname()[1]
        owner={'workers':[],'children':[],'pid':os.getpid(),'pgid':os.getpgrp(),'port':port}
        (output/'runtime-owner.json').write_text(json.dumps(owner))
        signal_times=[];signal_wall=[]
        def interrupt():
            signal_times.append(time.monotonic());signal_wall.append(int(time.time()*1000));os.kill(os.getpid(),signal.SIGTERM)
        timer=threading.Timer(.2,interrupt);start=time.monotonic()
        try:
            with Deadline(work_seconds=5,total_seconds=10,signal_seconds=3) as budget:
                budget.begin_cleanup();timer.start()
                cleanup=cleanup_owned_runtime(output,owner,budget,compose=None,env=None,ports=[port])
                assert signal_times and budget.interrupted
                observations=json.loads((output/'port-cleanup.json').read_text())['observations']
                signal_during_wait=bool(observations and observations[0]['at_ms']<signal_wall[0])
                assert signal_during_wait
                assert cleanup['status']=='failed' and cleanup['remaining']==[f'listener:{port}']
                (output/'failure.json').write_text(json.dumps({'error':'late cleanup signal'}))
                result=publish_evidence(root,output,'0'*40,root/'sealed',budget=budget)
            sealed=root/'sealed'/root.name/('0'*40)
            verify_manifest(sealed);read_fingerprint_authority(sealed)
            elapsed=time.monotonic()-start
            receipt={'elapsed_seconds':elapsed,'after_signal_seconds':time.monotonic()-signal_times[0],'signal_during_port_wait':signal_during_wait,'sealed_failure':result==1}
            (root/'receipt.json').write_text(json.dumps(receipt))
            assert elapsed<2,receipt
        finally:
            timer.cancel();timer.join();listener.close()
        with socket.socket() as verification:verification.bind(('127.0.0.1',port))
    """))
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    assert result.returncode == 0, result.stderr
