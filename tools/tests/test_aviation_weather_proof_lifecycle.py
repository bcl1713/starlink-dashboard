"""Real process failure controls; no scientific decoding or fake GPU evidence."""

import json
import shutil
import subprocess
import sys
import textwrap

import pytest


def run_control(tmp_path, body, *, python=sys.executable):
    script = tmp_path / "control.py"
    script.write_text(textwrap.dedent(body))
    result = subprocess.run(
        [python, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((tmp_path / "receipt.json").read_text())


@pytest.mark.parametrize("ignore_term", [False, True])
def test_dead_leader_descendant_is_stopped_reaped_and_force_is_recorded(
    tmp_path, ignore_term
):
    receipt = run_control(
        tmp_path,
        f"""
        import json, os, subprocess, sys, time
        from pathlib import Path
        from acceptance.aviation_weather_proof.lifecycle import enable_subreaper, stop_owned_groups
        enable_subreaper()
        root = Path(sys.argv[1])
        code = "import os,signal,time; p=os.fork(); (os._exit(0) if p else None); signal.signal(signal.SIGTERM, signal.SIG_IGN if {ignore_term!r} else signal.SIG_DFL); open({str(tmp_path / 'pid')!r},'w').write(str(os.getpid())); time.sleep(30)"
        leader = subprocess.Popen([sys.executable, '-c', code], start_new_session=True)
        try:
            leader.wait(timeout=2)
            until=time.monotonic()+2
            while not (root/'pid').exists() and time.monotonic()<until: time.sleep(.01)
            assert (root/'pid').exists()
            pid=int((root/'pid').read_text())
            result=stop_owned_groups([leader.pid], grace=.1, seconds=2)
            assert not Path('/proc',str(pid)).exists()
            (root/'receipt.json').write_text(json.dumps(result))
        finally:
            try: os.killpg(leader.pid,9)
            except ProcessLookupError: pass
    """,
    )
    assert receipt["remaining"] == []
    assert bool(receipt["killed_descendants"]) == ignore_term


@pytest.mark.parametrize("interrupt", ["deadline", "SIGTERM", "SIGINT"])
def test_budget_interrupt_reserves_cleanup_and_retains_failure(tmp_path, interrupt):
    receipt = run_control(
        tmp_path,
        f"""
        import json, os, signal, sys, time
        from pathlib import Path
        from acceptance.aviation_weather_proof.lifecycle import Deadline
        root=Path(sys.argv[1]); start=time.monotonic()
        with Deadline(work_seconds=.15, total_seconds=3, signal_seconds=2) as budget:
            try:
                if {interrupt!r} != 'deadline': os.kill(os.getpid(),getattr(signal,{interrupt!r}))
                time.sleep(5)
                raise AssertionError('work did not stop')
            except (TimeoutError, InterruptedError) as error:
                failure=str(error)
            finally:
                budget.begin_cleanup()
                assert budget.remaining() > 1
                time.sleep(.05)
                (root/'receipt.json').write_text(json.dumps({{'failed':bool(failure),'elapsed':time.monotonic()-start}}))
    """,
    )
    assert receipt["failed"]
    assert receipt["elapsed"] < 1


def test_browser_wrapper_reaps_dead_journey_leader_and_closes_owned_session(tmp_path):
    receipt = run_control(
        tmp_path,
        """
        import json, os, subprocess, sys
        from pathlib import Path
        from unittest.mock import patch
        from acceptance.aviation_weather_proof.lifecycle import Deadline
        from acceptance.aviation_weather_proof.run_browser import execute
        root=Path(sys.argv[1]); original=subprocess.Popen
        browser=original([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
        xvfb=original([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
        class Session:
            metrics={};webgl2={};artifacts={};cdp_url='http://127.0.0.1:1';display=':unit'
            profile_dir=root/'profile';_browser=browser;_browser_group=browser.pid;_xvfb=xvfb
            closed=False
            def close(self): self.closed=True
        session=Session()
        def start(argv,**kwargs):
            assert argv[0]=='node'
            code='import os,time; p=os.fork(); (os._exit(0) if p else None); time.sleep(30)'
            return original([sys.executable,'-c',code],**kwargs)
        try:
            with patch('acceptance.platform.runner._load_profile',return_value=object()), patch('acceptance.platform.health.start_final_browser_session',return_value=session), patch('subprocess.Popen',side_effect=start), Deadline(work_seconds=3,total_seconds=6) as budget:
                assert execute(['--origin','http://127.0.0.1:15290','--artifacts',str(root),'--profile','unused'],budget)==0
            assert session.closed
            assert not Path('/proc',str(browser.pid)).exists()
            assert not Path('/proc',str(xvfb.pid)).exists()
            receipt=json.loads((root/'browser-cleanup.json').read_text())
            (root/'receipt.json').write_text(json.dumps(receipt))
        finally:
            for child in (browser,xvfb):
                try: os.killpg(child.pid,9)
                except ProcessLookupError: pass
                child.wait(timeout=2)
    """,
        python=shutil.which("python3"),
    )
    assert receipt["remaining"] == []
    assert receipt["killed_descendants"] == []
    assert receipt["status"] == "passed"
