"""Provisioned native browser authority; preserve start failures and reap children."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]


def validate_arguments(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for key in ('origin', 'artifacts', 'profile'):
        parser.add_argument('--' + key)
    result = parser.parse_args(arguments)
    url = urlparse(result.origin or '')
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('loopback origin required')
    if not result.artifacts or not result.profile:
        raise ValueError('artifacts and provisioned profile required')
    return result


def execute(arguments: list[str]) -> int:
    from acceptance.platform.health import PlatformHealthExecutor, start_final_browser_session
    from acceptance.platform.runner import _load_profile, _probe
    args = validate_arguments(arguments)
    output = Path(args.artifacts)
    output.mkdir(parents=True, exist_ok=True)
    session = None
    child = None
    stop_metrics = threading.Event()
    monitor = None
    measurements: list[dict] = []
    cleanup: dict = {'status': 'pending', 'killed_descendants': [], 'remaining': []}
    try:
        session = start_final_browser_session(_load_profile(Path(args.profile)), output/'platform', PlatformHealthExecutor(probe=_probe))
        (output/'platform.json').write_text(json.dumps({'metrics': session.metrics, 'webgl2': session.webgl2}, indent=2))
        command = ['node', str(ROOT/'tools/acceptance/aviation_weather_proof/journey.mjs'), '--session', session.cdp_url, '--origin', args.origin, '--artifacts', str(output)]
        (output/'journey-owner.json').write_text(json.dumps({'command':command,'parent_pid':os.getpid(),'session_cdp':session.cdp_url}))
        browser_group = session._browser_group
        (output/'browser-owner.json').write_text(json.dumps({'browser_pid':session._browser.pid,'browser_pgid':browser_group,'xvfb_pid':session._xvfb.pid,'cdp_url':session.cdp_url,'profile_directory':str(session.profile_dir),'display':session.display}))
        child = subprocess.Popen(command, start_new_session=True)
        groups = {browser_group, child.pid, os.getpgid(session._xvfb.pid)}
        def measure():
            while not stop_metrics.is_set():
                records=[]
                for entry in Path('/proc').iterdir():
                    if not entry.name.isdigit(): continue
                    try:
                        fields=(entry/'stat').read_text().rsplit(')',1)[1].split()
                        group=int(fields[2])
                        if group not in groups:continue
                        # stat fields after comm: state=3, pgrp=5, utime=14,
                        # stime=15, rss=24. RSS is resident pages.
                        records.append({'pid':int(entry.name),'pgid':group,'cpu_seconds':(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'),'rss_bytes':int(fields[21])*os.sysconf('SC_PAGE_SIZE')})
                    except (OSError,ValueError,IndexError):continue
                measurements.append({'monotonic':time.monotonic(),'processes':records})
                stop_metrics.wait(.5)
        monitor=threading.Thread(target=measure,name='aviation-owned-resource-monitor')
        monitor.start()
        (output/'journey-process.json').write_text(json.dumps({'pid':child.pid,'pgid':child.pid}))
        return child.wait(timeout=600)
    except BaseException as error:
        retained = getattr(error, 'platform_artifacts', {})
        for name, content in retained.items():
            destination = output/'platform'/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        (output/'browser-start-or-journey-failure.json').write_text(json.dumps({'error':str(error),'cleanup_error':getattr(error,'platform_cleanup_error','')}))
        raise
    finally:
        stop_metrics.set()
        if monitor is not None: monitor.join(timeout=5)
        (output/'process-metrics.json').write_text(json.dumps(measurements,indent=2))
        try:
            if child is not None:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        cleanup['killed_descendants'].append(child.pid)
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)
                # A dead leader alone does not establish its group is gone.
                try:
                    os.killpg(child.pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    cleanup['remaining'].append(child.pid)
            if session is not None:
                session.close()
            cleanup['status']='passed' if not cleanup['remaining'] and not cleanup['killed_descendants'] else 'failed'
        except BaseException as error:
            cleanup.update(status='failed',error=str(error))
            raise
        finally:
            if session is not None:
                for name, content in session.artifacts.items():
                    destination=output/'platform'/name
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_bytes(content)
            (output/'browser-cleanup.json').write_text(json.dumps(cleanup,indent=2))


def main() -> int:
    def interrupted(signum, _frame):
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    return execute(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
