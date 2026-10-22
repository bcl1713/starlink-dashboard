"""Offline Stage 1 identity gates: real pinned Git objects, synthetic patches only."""

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import build  # noqa: E402

REPO = PACKAGE.parents[2]


class IdentityTests(unittest.TestCase):
    def test_full_pins_resolve(self):
        for sha in build.PINS.values():
            self.assertEqual(
                build.git(REPO, "rev-parse", sha + "^{commit}").decode().strip(), sha
            )
            self.assertEqual(len(sha), 40)

    def test_wrong_role_sha_and_short_sha(self):
        for role, sha in [
            ("A", build.PINS["C"]),
            ("C", build.PINS["implementation"]),
            ("A", "25e34168"),
            ("B", build.PINS["A"]),
        ]:
            with self.subTest(role=role, sha=sha), self.assertRaises(build.GuardError):
                build.verify_role(REPO, role, sha)

    def test_exact_exports_and_dirty_export(self):
        for role in ("A", "C"):
            with self.subTest(role=role), tempfile.TemporaryDirectory(
                prefix="perf391-stage1-"
            ) as tmp:
                root = Path(tmp) / "source"
                result = build.export_source(REPO, role, build.PINS[role], root)
                raw = build.git(REPO, "archive", "--format=tar", build.PINS[role])
                self.assertEqual(root.with_suffix(".tar").read_bytes(), raw)
                self.assertEqual(
                    result["archive_sha256"], hashlib.sha256(raw).hexdigest()
                )
                build.verify_export(REPO, role, root)
                (root / "unexpected").write_text("dirty")
                with self.assertRaises(build.GuardError):
                    build.verify_export(REPO, role, root)
                with self.assertRaises(build.GuardError):
                    build.export_source(REPO, role, build.PINS[role], root)

    def test_dirty_worktree_and_wrong_head(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage1-") as tmp:
            root = Path(tmp)
            build.git(root, "init", "-q")
            build.git(root, "config", "user.email", "fixture@example.invalid")
            build.git(root, "config", "user.name", "Fixture")
            (root / "file").write_text("clean")
            build.git(root, "add", ".")
            build.git(root, "commit", "-qm", "fixture")
            sha = build.git(root, "rev-parse", "HEAD").decode().strip()
            build.verify_clean_worktree(root, sha)
            with self.assertRaises(build.GuardError):
                build.verify_clean_worktree(root, build.PINS["A"])
            for name in ("file", "untracked", "ignored"):
                (root / name).write_text("dirty")
                with self.assertRaises(build.GuardError):
                    build.verify_clean_worktree(root, sha)
                (root / name).unlink()
                (root / "file").write_text("clean")

    def test_runtime_equivalence_and_frontend_identity(self):
        result = build.verify_equivalence(REPO)
        self.assertTrue(result["corrected_runtime_equal"])
        self.assertTrue(result["frontend_equal"])

    def test_frozen_collector_and_release(self):
        for kind in ("collector", "harness"):
            files = build.reference_files(REPO, kind)
            self.assertGreater(len(files), 10)
            build.verify_dependency(REPO, kind, build.PINS[kind], files)
            with self.assertRaises(build.GuardError):
                build.verify_dependency(REPO, kind, build.PINS["C"], files)
            changed = copy.deepcopy(files)
            key = next(iter(changed))
            changed[key]["sha256"] = "0" * 64
            with self.assertRaises(build.GuardError):
                build.verify_dependency(REPO, kind, build.PINS[kind], changed)
            changed = copy.deepcopy(files)
            changed["unexpected"] = changed[key]
            with self.assertRaises(build.GuardError):
                build.verify_dependency(REPO, kind, build.PINS[kind], changed)
        build.verify_collector_release(REPO)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="perf391-stage1-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        self.name = "backend/starlink-location/app/fixture.py"
        p = self.root / self.name
        p.parent.mkdir(parents=True)
        p.write_bytes(b"one\ntwo\nthree\n")
        self.patch = (
            f"diff --git a/{self.name} b/{self.name}\n--- a/{self.name}\n+++ b/{self.name}\n@@ -1,3 +1,3 @@\n one\n-two\n+TWO\n three\n"
        ).encode()
        self.spec = {
            "base_tree_sha256": build.tree_manifest(self.root)["tree_sha256"],
            "sha256": build.digest(self.patch),
            "files": {
                self.name: {
                    "before": build.digest(p.read_bytes()),
                    "after": build.digest(b"one\nTWO\nthree\n"),
                }
            },
        }

    def test_exact_patch_and_tree_hashes(self):
        before = build.tree_manifest(self.root)
        result = build.apply_patch(self.root, self.patch, self.spec)
        self.assertEqual((self.root / self.name).read_bytes(), b"one\nTWO\nthree\n")
        self.assertNotEqual(before, result)
        self.assertEqual(result, build.tree_manifest(self.root))

    def test_patch_drift(self):
        with self.assertRaises(build.GuardError):
            build.apply_patch(self.root, self.patch + b"\n", self.spec)

    def test_offset_fuzz_and_no_partial_mutation(self):
        for content in (b"prefix\none\ntwo\nthree\n", b"wrong\ntwo\nthree\n"):
            (self.root / self.name).write_bytes(content)
            self.spec["files"][self.name]["before"] = build.digest(content)
            before = build.tree_manifest(self.root)
            self.spec["base_tree_sha256"] = before["tree_sha256"]
            with self.assertRaises(build.GuardError):
                build.apply_patch(self.root, self.patch, self.spec)
            self.assertEqual(build.tree_manifest(self.root), before)

    def test_unexpected_file_and_wrong_postimage(self):
        for mutate in ("extra", "after"):
            spec = copy.deepcopy(self.spec)
            if mutate == "extra":
                spec["files"]["other.py"] = spec["files"][self.name]
            else:
                spec["files"][self.name]["after"] = "0" * 64
            with self.assertRaises(build.GuardError):
                build.apply_patch(self.root, self.patch, spec)
            self.assertEqual((self.root / self.name).read_bytes(), b"one\ntwo\nthree\n")

    def test_protected_paths_and_symlinks(self):
        for name in (
            "../escape.py",
            "/tmp/escape.py",
            "backend/starlink-location/Dockerfile",
            "frontend/mission-planner/package.json",
            "tools/acceptance/performance_availability/run.py",
            "tools/diagnostics/perf391-network-evidence-v1/browser.mjs",
        ):
            with self.subTest(name=name), self.assertRaises(build.GuardError):
                build.check_patch_path(name)
        p = self.root / self.name
        p.unlink()
        p.symlink_to("/etc/hosts")
        with self.assertRaises(build.GuardError):
            build.apply_patch(self.root, self.patch, self.spec)

    def test_unexpected_source_tree_change(self):
        (self.root / "unrelated").write_text("unreviewed")
        with self.assertRaises(build.GuardError):
            build.apply_patch(self.root, self.patch, self.spec)
        self.assertEqual((self.root / self.name).read_bytes(), b"one\ntwo\nthree\n")

    def test_frontend_patch_agreement(self):
        name = "frontend/mission-planner/src/fixture.ts"
        common = {
            "sha256": "1" * 64,
            "base_tree_sha256": "2" * 64,
            "files": {name: {"before": "3" * 64, "after": "4" * 64}},
        }
        build.verify_frontend_patch_agreement(common, copy.deepcopy(common))
        for mutation in ("target", "after", "before"):
            changed = copy.deepcopy(common)
            if mutation == "target":
                changed["files"][name + "x"] = changed["files"].pop(name)
            else:
                changed["files"][name][mutation] = "5" * 64
            with self.subTest(mutation=mutation), self.assertRaises(build.GuardError):
                build.verify_frontend_patch_agreement(common, changed)

    def test_primary_import_contamination(self):
        build.verify_primary(self.root)
        (self.root / self.name).write_text("import backend_probe\n")
        with self.assertRaises(build.GuardError):
            build.verify_primary(self.root)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = build.manifest_template(
            "C", build.PINS["plan"], build.PINS["base"], "1" * 64, "2" * 64, "3" * 64
        )

    def test_valid_manifest_and_missing_or_wrong_labels(self):
        build.validate_manifest(self.manifest)
        for label in self.manifest["labels"]:
            for value in (None, "incorrect"):
                candidate = copy.deepcopy(self.manifest)
                if value is None:
                    del candidate["labels"][label]
                else:
                    candidate["labels"][label] = value
                with self.subTest(label=label, value=value), self.assertRaises(
                    build.GuardError
                ):
                    build.validate_manifest(candidate)

    def test_identity_and_closed_manifest(self):
        for key, value in [
            ("collector_source_sha", build.PINS["C"]),
            ("base_application_sha", build.PINS["implementation"]),
            ("role", "B"),
            ("extra", True),
            ("image_built", True),
            ("integration_source_sha", "short"),
        ]:
            candidate = copy.deepcopy(self.manifest)
            candidate[key] = value
            with self.subTest(key=key), self.assertRaises(build.GuardError):
                build.validate_manifest(candidate)


if __name__ == "__main__":
    unittest.main()
