"""A timeout must enter the replay runner's finally and reap new-session children."""

import asyncio
import json
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_stage4 import COLLECTOR  # initializes the package import path

from owner import Owner


class Stage5SignalTests(unittest.IsolatedAsyncioTestCase):
    async def test_term_of_replay_runner_reaps_its_separate_session_child(self):
        self.assertIsNotNone(COLLECTOR)
        with tempfile.TemporaryDirectory(prefix="perf391-stage5-signal-") as tmp:
            root = Path(tmp)
            script = """import runpy,sys
sys.path[:0]=['.', 'tests']
from owner import Owner
original=Owner.spawn
def spawn(self, command, **kwargs):
    child=original(self,[sys.executable,'-c','import signal;signal.pause()'],**kwargs)
    print(child.pid,flush=True)
    return child
Owner.spawn=spawn
sys.argv=['tests/stage5_qualify.py','--output',sys.argv[1]]
runpy.run_path('tests/stage5_qualify.py',run_name='__main__')
"""
            owner = Owner(
                root / "test-owner",
                run="synthetic-stage5",
                sources={},
                adopt_descendants=True,
            )
            with (root / "runner.py").open("w") as stream:
                stream.write(script)
            child = owner.spawn(
                [sys.executable, "-B", str(root / "runner.py"), str(root / "run")],
                stdout=subprocess.PIPE,
            )
            try:
                line = await asyncio.wait_for(
                    asyncio.to_thread(child.stdout.readline), timeout=10
                )
                self.assertTrue(line, "runner did not reach owned child")
                nested = int(line)
                child.send_signal(signal.SIGTERM)
                await asyncio.to_thread(child.wait, timeout=10)
                self.assertFalse(
                    Path(f"/proc/{nested}").exists(), "timeout escaped scoped cleanup"
                )
                manifest = json.loads((root / "run/manifest.json").read_bytes())
                self.assertEqual(manifest["status"], "clean")
            finally:
                child.stdout.close()
                await owner.close()
