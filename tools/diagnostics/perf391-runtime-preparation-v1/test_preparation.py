"""Offline design validation only: synthetic built-receipt fixtures, never images."""

import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prepare import HERE, sha, write, verify_overlay, check_release
from launcher import launch_plan, validate_receipt
from runtime_identity import DIAGNOSTIC_NODE_SHA256, verify_runtime_overlay


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = Path(os.environ["PERF391_OFFLINE_ROOT"])
        cls.plan_path = cls.output / "runtime-build-plan.json"
        cls.plan = json.loads(cls.plan_path.read_bytes())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="perf391-prep-test-")
        self.addCleanup(self.temp.cleanup)
        self.assets = Path(self.temp.name) / "assets"
        self.assets.mkdir()
        (self.assets / "index.html").write_text("synthetic offline fixture only")
        (self.assets / "assets").mkdir()
        (self.assets / "assets/fixture.js").write_text("synthetic offline fixture only")
        (self.assets / ".vite").mkdir()
        write(
            self.assets / ".vite/manifest.json",
            {"index.html": {"file": "assets/fixture.js"}},
        )
        modules = [
            "diagnostic/browser-runtime.ts",
            "diagnostic/browser-probe.ts",
            "src/hooks/api/useOverviewHistory.ts",
            "src/services/overview-history.ts",
            "src/pages/OverviewMetricHistoryPanel.tsx",
        ]
        write(
            self.assets / "perf391-module-closure.json",
            {
                "schema": "perf391-compiled-modules-v1",
                "modules": {
                    "assets/fixture.js": [
                        {"id": name, "renderedLength": 1} for name in modules
                    ]
                },
            },
        )
        self.receipt = {
            "schema": "perf391-runtime-receipt-v1",
            "role": "A",
            "plan_sha256": sha(self.plan_path),
            "images": {
                name: {
                    "id": "sha256:" + digit * 64,
                    "labels": dict(self.plan["roles"]["A"]["labels"]),
                    "repo_digests": [],
                }
                for name, digit in (("backend", "1"), ("frontend", "2"))
            },
            "assets": {
                p.relative_to(self.assets).as_posix(): sha(p)
                for p in self.assets.rglob("*")
                if p.is_file()
            },
            "asset_root": str(self.assets),
            "dependencies": {
                "python_freeze_sha256": "3" * 64,
                "npm_lock_sha256": self.plan["roles"]["A"]["package_lock_sha256"],
                "os_packages_sha256": "4" * 64,
                "browser_tree_sha256": "5" * 64,
            },
            "browser": {
                "playwright": "1.63.0",
                "chromium_sha256": "6" * 64,
                "node_sha256": DIAGNOSTIC_NODE_SHA256,
                "node_version": "22.22.2",
                "playwright_root": "/synthetic/offline-only",
                "chromium_executable": "/synthetic/offline-only/chrome",
            },
        }

    def validate(self, receipt=None):
        validate_receipt(receipt or self.receipt, self.plan, sha(self.plan_path))

    def test_full_frozen_release_and_runtime_overlay(self):
        self.assertEqual(check_release()["verified_files"], 621)
        verify_runtime_overlay(self.plan)

    def test_exact_derivative_identities_and_unbuilt_claims(self):
        for role, expected in (
            ("A", "015c5f515438b7114f903e90c5c43014a2b29fb6c316fdbca0232681585c5baa"),
            ("C", "4f1913894101595ab96bdd289bd80f88a6dcb95c058d0851cb3e4e025ae13f4a"),
        ):
            self.assertEqual(
                self.plan["roles"][role]["identity"]["effective_source_sha256"],
                expected,
            )
            self.assertEqual(self.plan["roles"][role]["labels"]["diagnostic"], "true")
        self.assertIsNone(self.plan["compiled_assets"])
        self.assertIsNone(self.plan["image_ids"])

    def test_proposed_python_is_syntax_only(self):
        for path in [*HERE.glob("*.py"), *HERE.glob("*.proposed.py")]:
            ast.parse(path.read_bytes(), filename=str(path))

    def test_synthetic_receipt_fixture_is_accepted_offline(self):
        self.validate()

    def test_wrong_role_collector_plan_or_node_fails(self):
        mutations = [
            lambda r: r["images"]["frontend"]["labels"].update({"perf391.role": "C"}),
            lambda r: r["images"]["backend"]["labels"].update(
                {"collector_source_sha": "a" * 40}
            ),
            lambda r: r.update(plan_sha256="b" * 64),
            lambda r: r["browser"].update(node_version="22.12.0"),
            lambda r: r["images"]["backend"].update(id="sha256:" + "0" * 64),
        ]
        for mutate in mutations:
            r = copy.deepcopy(self.receipt)
            mutate(r)
            with self.subTest(receipt=r), self.assertRaises(ValueError):
                self.validate(r)

    def test_asset_changes_extras_and_symlinks_fail(self):
        fixture = self.assets / "assets/fixture.js"
        fixture.write_text("changed")
        with self.assertRaises(ValueError):
            self.validate()
        fixture.write_text("synthetic offline fixture only")
        extra = self.assets / "unexpected.js"
        extra.write_text("extra")
        with self.assertRaises(ValueError):
            self.validate()
        extra.unlink()
        fixture.unlink()
        fixture.symlink_to(self.assets / "index.html")
        with self.assertRaises(ValueError):
            self.validate()

    def test_compiled_probe_absence_fails_even_with_rehashed_file(self):
        path = self.assets / "perf391-module-closure.json"
        data = json.loads(path.read_bytes())
        data["modules"]["assets/fixture.js"].pop(1)
        write(path, data)
        self.receipt["assets"][path.name] = sha(path)
        with self.assertRaises(ValueError):
            self.validate()

    def test_both_launch_plans_are_isolated_bounded_and_five_samples(self):
        seen = set()
        for role in ("A", "C"):
            plan = launch_plan(
                role, "/tmp/perf391-smoke-408-" + role.lower(), self.plan_path
            )
            ports = set(plan["ownership"]["ports"])
            self.assertFalse(ports & seen)
            seen |= ports
            self.assertFalse(plan["compose"]["base"]["networks"]["default"]["internal"])
            self.assertEqual(plan["browser_options"]["samples"], 5)
            self.assertEqual(plan["deadlines"]["outer_timeout_seconds"], 90)
            self.assertEqual(plan["deadlines"]["kill_grace_seconds"], 10)
            self.assertFalse(plan["runtime_authorized"])
            self.assertTrue(
                all(
                    "build" not in s
                    for s in plan["compose"]["base"]["services"].values()
                )
            )

    def test_offline_launcher_refuses_execution_without_reading_plan(self):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(HERE / "launcher.py"),
                "--role",
                "A",
                "--plan",
                "/missing",
                "--root",
                "/tmp/perf391-smoke-408-a",
                "--execute",
            ],
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"preparation checkpoint only", result.stderr)

    def test_overlay_drift_and_existing_root_fail(self):
        plan = copy.deepcopy(self.plan)
        plan["overlay_files"]["launcher.py"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_overlay(plan)
        with self.assertRaises(ValueError):
            launch_plan("A", self.assets, self.plan_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
