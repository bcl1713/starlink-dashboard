"""Actual proposed executor + real process Owner; fake Docker only.

Every spawned argv is replaced with a Python fixture. No Docker, application,
network listener or browser process can execute in these tests.
"""

import asyncio
import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from launcher import launch_plan
from prepare import HERE, write
from test_node_identity import BUILT, NODE_HASH, PLAN_PATH

Owner = importlib.import_module("owner").Owner  # prepare establishes its source path

spec = importlib.util.spec_from_file_location(
    "proposed_executor", HERE / "execute.proposed.py"
)
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)

FAKE = r"""
import json,os,signal,sys,time,shutil
from pathlib import Path
argv=json.loads(sys.argv[1]); root=Path(sys.argv[2]); scenario=sys.argv[3]
if argv[0]=='timeout': argv=argv[3:]
with (root/'commands.jsonl').open('a') as f: f.write(json.dumps(argv)+'\n')
if argv[-1:] == ['--version']: print('22.22.2'); sys.exit(0)
if argv[:3]==['docker','image','inspect']:
 if scenario=='missing-image': sys.exit(1)
 receipt=json.loads((root/'receipt.json').read_bytes())
 image=next(i for i in receipt['images'].values() if i['id']==argv[3])
 print(json.dumps({'Id':image['id'],'Config':{'Labels':image['labels']}})); sys.exit(0)
if argv[:2]==['docker','cp']:
 receipt=json.loads((root/'receipt.json').read_bytes())
 shutil.copytree(receipt['asset_root'],argv[-1],dirs_exist_ok=True); sys.exit(0)
if argv[:2]==['docker','ps']: sys.exit(0)
if 'compose' in argv and 'down' in argv:
 sys.exit(1 if scenario=='cleanup-failure' else 0)
if scenario.startswith('frontend-'):
 if '-c' in argv:
  if scenario=='frontend-delayed' and not (root/'refused').exists():
   (root/'refused').touch(); print('ConnectionRefusedError: refused'); sys.exit(1)
  receipt=json.loads((root/'receipt.json').read_bytes())
  print(json.dumps({'status':200,'sha256':receipt['assets']['index.html']})); sys.exit(0)
 if 'compose' in argv and 'up' in argv:
  if 'mission-planner' in argv and scenario=='frontend-sigterm':
   os.kill(os.getppid(),signal.SIGTERM); time.sleep(30)
  sys.exit(0)
 if 'compose' in argv and 'ps' in argv: print('frontend-id'); sys.exit(0)
 if argv[:2]==['docker','inspect']:
  ready=scenario in ('frontend-ready','frontend-delayed')
  print(json.dumps({'Running':ready,'Status':'running' if ready else 'exited','ExitCode':0 if ready else 7})); sys.exit(0)
 if 'compose' in argv and 'logs' in argv: print('nginx fixture failure'); sys.exit(0)
 if argv[:2]==['docker','port']: print('80/tcp -> 127.0.0.1:38080'); sys.exit(0)
if 'compose' in argv and 'up' in argv:
 if scenario=='sigterm':
  os.kill(os.getppid(),signal.SIGTERM)
  time.sleep(30)
 sys.exit(1)
"""


class ExecutorTests(unittest.TestCase):
    def run_case(self, scenario, mutate=None, expected_preflight=False):
        with tempfile.TemporaryDirectory(prefix="perf391-executor-fixture-") as temp:
            fixture = Path(temp)
            root = Path("/tmp/perf391-smoke-408-" + fixture.name)
            self.addCleanup(
                lambda: __import__("shutil").rmtree(root, ignore_errors=True)
            )
            receipt = json.loads((BUILT / "evidence/built-A.json").read_bytes())
            launch = launch_plan("A", root, PLAN_PATH, receipt)
            write(fixture / "launch.json", launch)
            if mutate:
                mutate(receipt)
            write(fixture / "receipt.json", receipt)
            (fixture / "fake.py").write_text(FAKE)
            args = SimpleNamespace(
                launch_plan=fixture / "launch.json",
                receipt=fixture / "receipt.json",
                build_plan=PLAN_PATH,
                node=Path("/fixture/node"),
                authorization="https://github.com/bcl1713/starlink-dashboard/pull/408#offline-test",
            )
            owners = []
            real_spawn = Owner.spawn

            class OfflineOwner(Owner):
                def __init__(self, *a, **kw):
                    kw["adopt_descendants"] = False
                    super().__init__(*a, **kw)
                    owners.append(self)

                def spawn(self, argv, **kw):
                    if scenario == "frontend-diagnostics-fail" and "logs" in argv:
                        raise OSError("offline diagnostic failure")
                    if scenario == "spawn-error" and "compose" in argv and "up" in argv:
                        raise OSError("offline injected spawn failure")
                    return real_spawn(
                        self,
                        [
                            sys.executable,
                            "-B",
                            str(fixture / "fake.py"),
                            json.dumps(argv),
                            str(fixture),
                            scenario,
                        ],
                        **kw,
                    )

            real_sha = executor.sha

            def fixture_sha(path):
                return NODE_HASH if Path(path) == args.node else real_sha(path)

            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(executor, "LOCK_PATH", fixture / "lock")
                )
                stack.enter_context(patch.object(executor, "verify_runtime_overlay"))
                stack.enter_context(
                    patch.object(
                        executor,
                        "verify_runtime_identity",
                        return_value={"offline_fixture": True},
                    )
                )
                stack.enter_context(patch.object(executor, "check_release"))
                stack.enter_context(
                    patch.object(executor, "sha", side_effect=fixture_sha)
                )
                stack.enter_context(
                    patch.object(
                        executor,
                        "browser_tree",
                        return_value=receipt["dependencies"]["browser_tree_sha256"],
                    )
                )
                stack.enter_context(
                    patch.object(
                        (
                            executor.build
                            if hasattr(executor, "build")
                            else __import__("build")
                        ),
                        "tree_manifest",
                        return_value={
                            "tree_sha256": json.loads(PLAN_PATH.read_bytes())["roles"][
                                "A"
                            ]["context_sha256"]
                        },
                    )
                )
                stack.enter_context(
                    patch.object(
                        executor, "socket", SimpleNamespace(socket=MagicMock())
                    )
                )
                stack.enter_context(patch.object(executor.ctypes, "CDLL"))
                executor.ctypes.CDLL.return_value.prctl.return_value = 0
                stack.enter_context(patch("owner.Owner", OfflineOwner))
                stack.enter_context(
                    patch(
                        "collector.prepare_collector",
                        side_effect=RuntimeError("offline after readiness"),
                    )
                )
                with self.assertRaises(Exception) as caught:
                    asyncio.run(executor.execute(args))
                if not expected_preflight:
                    self.assertTrue(
                        (root / "runtime-result.json").exists(), repr(caught.exception)
                    )
            if expected_preflight:
                self.assertEqual(owners, [])
                self.assertFalse(root.exists())
                return
            result = json.loads((root / "runtime-result.json").read_bytes())
            commands = [
                json.loads(s)
                for s in (fixture / "commands.jsonl").read_text().splitlines()
            ]
            self.assertTrue(result["failure"])
            self.assertEqual(
                result["cleanup_error"],
                "RuntimeError" if scenario == "cleanup-failure" else None,
            )
            for owner in owners:
                self.assertEqual(owner.manifest["status"], "clean", owner.manifest)
                for child, record in owner.children:
                    self.assertIsNotNone(child.poll())
                    self.assertFalse(Path(f"/proc/{child.pid}").exists())
            downs = [c for c in commands if "down" in c]
            self.assertEqual(len(downs), 1)
            self.assertIn(launch["project"], downs[0])
            for c in commands:
                if c[:2] == ["docker", "compose"]:
                    self.assertEqual(c[2:4], ["-p", launch["project"]])
                self.assertNotIn("prune", c)
                self.assertNotIn("browser-owner.proposed.mjs", " ".join(c))
            if scenario == "missing-image":
                self.assertFalse(any("up" in c or "create" in c for c in commands))
            if scenario in ("frontend-ready", "frontend-delayed"):
                readiness = json.loads((root / "frontend-readiness.json").read_text())
                self.assertEqual(readiness["status"], "ready")
                self.assertIn("offline after readiness", result["failure"])
                self.assertEqual(
                    len(readiness["attempts"]),
                    2 if scenario == "frontend-delayed" else 1,
                )
            if scenario.startswith("frontend-"):
                snapshots = json.loads(
                    (root / "frontend-failure-diagnostics.json").read_text()
                )
                self.assertTrue(
                    any(
                        r["kind"] == "inspect" and "ExitCode" in r.get("output", "")
                        for r in snapshots
                    )
                )
                if scenario == "frontend-diagnostics-fail":
                    self.assertTrue(
                        any(
                            r["kind"] == "frontend-logs" and "error" in r
                            for r in snapshots
                        )
                    )
                else:
                    self.assertTrue(
                        any(
                            r["kind"] == "frontend-logs"
                            and "nginx fixture" in r.get("output", "")
                            for r in snapshots
                        )
                    )
                self.assertLess(
                    next(
                        i
                        for i, c in enumerate(commands)
                        if "inspect" in c and "image" not in c
                    ),
                    next(i for i, c in enumerate(commands) if "down" in c),
                )
            if scenario == "sigterm":
                self.assertIn("signal", result["failure"])
            return commands

    def test_missing_image_stops_before_container_creation_and_cleans(self):
        self.run_case("missing-image")

    def test_invalid_receipt_stops_before_ownership(self):
        self.run_case("invalid-receipt", lambda r: r.update(plan_sha256="0" * 64), True)

    def test_wrong_node_receipt_stops_before_ownership(self):
        for version, digest in [("22.12.0", NODE_HASH), ("22.22.2", "0" * 64)]:
            with self.subTest(version=version, digest=digest):
                self.run_case(
                    "wrong-node",
                    lambda r, version=version, digest=digest: r["browser"].update(
                        node_version=version, node_sha256=digest
                    ),
                    True,
                )

    def test_immediate_readiness_allows_next_phase(self):
        self.run_case("frontend-ready")

    def test_delayed_readiness_allows_next_phase(self):
        self.run_case("frontend-delayed")

    def test_failed_diagnostics_preserve_cleanup(self):
        self.run_case("frontend-diagnostics-fail")

    def test_frontend_exit_snapshots_before_cleanup(self):
        self.run_case("frontend-exit")

    def test_frontend_startup_signal_snapshots_before_cleanup(self):
        self.run_case("frontend-sigterm")

    def test_startup_failure_runs_scoped_cleanup(self):
        self.run_case("startup-failure")

    def test_spawn_failure_runs_scoped_cleanup(self):
        self.run_case("spawn-error")

    def test_sigterm_reaps_running_command_and_runs_scoped_cleanup(self):
        self.run_case("sigterm")

    def test_cleanup_failure_is_reported_and_processes_reaped(self):
        self.run_case("cleanup-failure")


if __name__ == "__main__":
    unittest.main(verbosity=2)
