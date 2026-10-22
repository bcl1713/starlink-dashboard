"""The offline test owner must also clean children after their leader exits."""

import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import run_backend


class RunnerCleanupTests(unittest.TestCase):
    def test_exited_leader_with_term_ignoring_descendant_is_cleaned(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage2-orphan-") as tmp:
            root = Path(tmp)
            identity = root / "child.json"
            descendant = 'import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready", flush=True); signal.pause()'
            leader = """import json, os, subprocess, sys
from pathlib import Path
child=subprocess.Popen([sys.executable,"-c",sys.argv[2]],stdout=subprocess.PIPE,text=True)
assert child.stdout.readline().strip()=="ready"
Path(sys.argv[1]).write_text(json.dumps({"pid":child.pid,"pgid":os.getpgid(child.pid),"start":Path(f"/proc/{child.pid}/stat").read_text().rsplit(")",1)[1].split()[19]}))
"""
            original_popen = subprocess.Popen

            def launch(command, **kwargs):
                if command[:4] == [sys.executable, "-B", "-m", "coverage"]:
                    command = [sys.executable, "-c", leader, str(identity), descendant]
                return original_popen(command, **kwargs)

            record = None
            try:
                with patch.object(
                    run_backend.subprocess, "Popen", launch
                ), contextlib.redirect_stdout(io.StringIO()):
                    result = run_backend.run(root / "result")
                record = json.loads(identity.read_text())
                owner = json.loads((root / "result/owner.json").read_text())
                self.assertEqual(result, 0)
                self.assertEqual(owner["status"], "clean")
                self.assertEqual(owner["live_group_survivors"], [])
                self.assertFalse(Path(f'/proc/{record["pid"]}').exists())
            finally:
                if record is None and identity.exists():
                    record = json.loads(identity.read_text())
                if record is not None:
                    path = Path(f'/proc/{record["pid"]}/stat')
                    if (
                        path.exists()
                        and path.read_text().rsplit(")", 1)[1].split()[19]
                        == record["start"]
                    ):
                        try:
                            os.kill(record["pid"], signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        deadline = time.monotonic() + 3
                        while path.exists() and time.monotonic() < deadline:
                            time.sleep(0.01)
                    self.assertFalse(path.exists(), "test-owned descendant not reaped")
