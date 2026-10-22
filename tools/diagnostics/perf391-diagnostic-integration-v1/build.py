"""Offline exact-source gates. This module deliberately has no image/run command.

Git objects supply exports; mutable worktrees never supply archive bytes. Patch
inputs are reviewed SHA-256/preimage/postimage specifications, not a glob. Text
hunks must match exact line positions and full context (no fuzz or offsets).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

PINS = {
    "A": "25e34168f0e2cecb149b0323f1f5a795cb28cae0",
    "C": "ee9ce1010e72e83cb6d4b8c79ecc15091b9d8832",
    "implementation": "3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc",
    "collector": "a48837b99d87366c6e3fc24ba2915f0b739cddad",
    "release": "c47d21e3c5bbf92189afbf291b73b9da7a035a4b",
    "harness": "f3029024b5950a267645195476da5cbca326f16a",
    "base": "33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96",
    "plan": "8aa7791bb03f0573cf602bdbfe8e43c085ee2325",
}
COLLECTOR = "tools/diagnostics/perf391-network-evidence-v1"
FROZEN = ("tools/acceptance/performance", "tools/acceptance/performance_availability")
RUNTIME = ("backend", "frontend", "tools", "monitoring", "scripts")
SCHEMA = "perf391-diagnostic-integration-v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")


class GuardError(ValueError):
    """An identity or source precondition failed; no build/run is allowed."""


def require(condition, message):
    if not condition:
        raise GuardError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, timeout=60
    )
    require(result.returncode == 0, result.stderr.decode(errors="replace"))
    return result.stdout


def verify_role(repo, role, sha):
    require(role in ("A", "C"), "unknown application role")
    require(sha == PINS[role], "wrong or abbreviated application SHA")
    require(
        git(repo, "rev-parse", sha + "^{commit}").decode().strip() == sha,
        "commit mismatch",
    )


def verify_clean_worktree(root, sha):
    require(
        git(root, "rev-parse", "HEAD").decode().strip() == sha, "wrong worktree HEAD"
    )
    require(
        not git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"),
        "dirty source worktree",
    )


def safe_path(name):
    p = PurePosixPath(name)
    require(
        bool(name) and not p.is_absolute() and ".." not in p.parts and str(p) == name,
        "unsafe path",
    )
    require(".git" not in p.parts and "\\" not in name, "unsafe Git/path component")
    return p


def archive_files(raw):
    """Read a Git tar without extracting it or following filesystem links."""
    result = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if member.isdir():
                continue
            safe_path(member.name)
            require(member.isfile(), "only regular source files are supported")
            require(member.name not in result, "duplicate archive path")
            result[member.name] = (
                archive.extractfile(member).read(),
                "100755" if member.mode & 0o111 else "100644",
            )
    require(bool(result), "empty archive")
    return result


def file_records(files):
    return {
        name: {"sha256": digest(data), "bytes": len(data), "mode": mode}
        for name, (data, mode) in sorted(files.items())
    }


def tree_manifest(root):
    root = Path(root)
    require(
        root.is_dir() and not root.is_symlink(), "source root is not a real directory"
    )
    files = {}
    for parent, dirs, names in os.walk(root, followlinks=False):
        for name in dirs:
            require(not (Path(parent) / name).is_symlink(), "symlink directory")
        for name in names:
            p = Path(parent) / name
            require(p.is_file() and not p.is_symlink(), "nonregular source file")
            relative = p.relative_to(root).as_posix()
            safe_path(relative)
            files[relative] = (
                p.read_bytes(),
                "100755" if p.stat().st_mode & 0o111 else "100644",
            )
    records = file_records(files)
    return {"files": records, "tree_sha256": digest(canonical(records))}


def export_source(repo, role, sha, destination):
    verify_role(repo, role, sha)
    root = Path(destination)
    tar_path = root.with_suffix(".tar")
    require(
        not root.exists() and not root.is_symlink() and not tar_path.exists(),
        "export destination already exists",
    )
    raw = git(repo, "archive", "--format=tar", sha)
    files = archive_files(raw)
    # Fail before writing if any archive member is unsupported or unsafe.
    root.mkdir(parents=True)
    tar_path.write_bytes(raw)
    for name, (data, mode) in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o755 if mode == "100755" else 0o644)
    result = verify_export(repo, role, root)
    return {
        "role": role,
        "base_application_sha": sha,
        "archive_sha256": digest(raw),
        **result,
    }


def verify_export(repo, role, root):
    require(role in ("A", "C"), "unknown role")
    expected = file_records(
        archive_files(git(repo, "archive", "--format=tar", PINS[role]))
    )
    actual = tree_manifest(root)
    require(
        actual["files"] == expected,
        "dirty export or wrong role: bytes/modes/file set differ",
    )
    return actual


def reference_files(repo, kind):
    require(kind in ("collector", "harness"), "unknown frozen dependency")
    paths = (COLLECTOR,) if kind == "collector" else FROZEN
    raw = git(repo, "archive", "--format=tar", PINS[kind], *paths)
    return file_records(archive_files(raw))


def verify_dependency(repo, kind, sha, files):
    require(
        kind in ("collector", "harness") and sha == PINS[kind],
        "wrong frozen dependency SHA",
    )
    require(
        files == reference_files(repo, kind),
        "frozen dependency file/hash/mode mismatch",
    )


def verify_collector_release(repo):
    release = json.loads(
        git(repo, "show", PINS["release"] + ":" + COLLECTOR + "/release-manifest.json")
    )
    require(
        release["collector_source_commit"] == PINS["collector"],
        "collector release source mismatch",
    )
    source = reference_files(repo, "collector")
    expected = {
        name.removeprefix(COLLECTOR + "/"): {"sha256": v["sha256"], "bytes": v["bytes"]}
        for name, v in source.items()
        if name != COLLECTOR + "/RESULTS.md"
    }
    require(release["files"] == expected, "collector release file inventory mismatch")
    require(
        release["frozen_harness_reference"] == PINS["harness"],
        "release harness mismatch",
    )
    return {
        "source_sha": PINS["collector"],
        "release_sha": PINS["release"],
        "manifest_sha256": digest(canonical(release)),
    }


def verify_equivalence(repo):
    roots = [
        archive_files(git(repo, "archive", "--format=tar", PINS[key]))
        for key in ("A", "C", "implementation")
    ]

    def frontend(files):
        return {k: v for k, v in files.items() if k.startswith("frontend/")}

    def runtime(files):
        return {
            k: v
            for k, v in files.items()
            if k.split("/")[0] in RUNTIME
            or (k.startswith("docker-compose") and "/" not in k)
        }

    require(frontend(roots[0]) == frontend(roots[1]), "A/C frontend disagreement")
    require(
        runtime(roots[1]) == runtime(roots[2]),
        "corrected delivery/implementation runtime drift",
    )
    return {
        "frontend_equal": True,
        "corrected_runtime_equal": True,
        "runtime_paths": list(RUNTIME) + ["docker-compose*"],
    }


def verify_frontend_patch_agreement(spec_a, spec_c):
    """Compare reviewed A/C frontend preimages/postimages independent of backend."""

    def frontend(spec):
        return {
            name: hashes
            for name, hashes in spec["files"].items()
            if name.startswith("frontend/")
        }

    require(
        frontend(spec_a) == frontend(spec_c), "A/C frontend patch/hash disagreement"
    )


def check_patch_path(name):
    safe_path(name)
    allowed = (
        name.startswith("backend/starlink-location/app/") and name.endswith(".py")
    ) or (
        name.startswith("frontend/mission-planner/src/")
        and name.endswith((".ts", ".tsx"))
    )
    require(allowed, "patch targets protected or nonapplication path")


def patched_bytes(original, hunks):
    """Apply a deliberately narrow, line-exact unified diff; never search context."""
    source = original.splitlines(keepends=True)
    output = []
    cursor = 0
    i = 0
    while i < len(hunks):
        match = re.fullmatch(
            rb"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n", hunks[i]
        )
        require(match is not None, "unsupported patch syntax")
        old_start, old_count, new_start, new_count = match.groups()
        old_count = int(old_count) if old_count is not None else 1
        new_count = int(new_count) if new_count is not None else 1
        position = int(old_start) - (1 if old_count else 0)
        require(cursor <= position <= len(source), "invalid or overlapping hunk")
        output.extend(source[cursor:position])
        require(
            len(output) == int(new_start) - (1 if new_count else 0),
            "new hunk offset drift",
        )
        cursor = position
        old_seen = new_seen = 0
        i += 1
        while i < len(hunks) and not hunks[i].startswith(b"@@ "):
            line = hunks[i]
            require(
                line[:1] in (b" ", b"-", b"+") and line.endswith(b"\n"),
                "unsupported hunk line",
            )
            if line[:1] in (b" ", b"-"):
                require(
                    cursor < len(source) and source[cursor] == line[1:],
                    "patch drift/fuzz/offset",
                )
                cursor += 1
                old_seen += 1
            if line[:1] in (b" ", b"+"):
                output.append(line[1:])
                new_seen += 1
            i += 1
        require((old_seen, new_seen) == (old_count, new_count), "hunk counts disagree")
    output.extend(source[cursor:])
    return b"".join(output)


def apply_patch(root, patch, spec):
    """Guarded synthetic/offline derivative patch; caller first verifies base export.

    Reviewed specs are immutable review inputs. No real A/C patch is shipped in
    Stage 1. Reject binary, rename, mode changes and no-newline patches explicitly.
    All output is validated before the first mutation.
    """
    require(
        set(spec) == {"sha256", "files", "base_tree_sha256"}
        and digest(patch) == spec["sha256"],
        "patch hash drift",
    )
    before = tree_manifest(root)
    require(
        before["tree_sha256"] == spec["base_tree_sha256"],
        "unexpected source tree change",
    )
    lines = patch.splitlines(keepends=True)
    i = 0
    pending = {}
    while i < len(lines):
        header = re.fullmatch(rb"diff --git a/([^\s]+) b/([^\s]+)\n", lines[i])
        require(
            header is not None and header[1] == header[2], "unsupported diff header"
        )
        name = header[1].decode("utf-8")
        check_patch_path(name)
        require(
            name not in pending and name in spec["files"],
            "unreviewed/duplicate patch target",
        )
        i += 1
        if i < len(lines) and lines[i].startswith(b"index "):
            require(
                re.fullmatch(
                    rb"index [0-9a-f]+\.\.[0-9a-f]+(?: 100(?:644|755))?\n", lines[i]
                )
                is not None,
                "invalid index line",
            )
            i += 1
        require(
            lines[i : i + 2]
            == [b"--- a/" + header[1] + b"\n", b"+++ b/" + header[1] + b"\n"],
            "unsupported file operation",
        )
        i += 2
        end = i
        while end < len(lines) and not lines[end].startswith(b"diff --git "):
            end += 1
        path = Path(root) / name
        require(name in before["files"] and path.is_file(), "missing preimage")
        entry = spec["files"][name]
        require(set(entry) == {"before", "after"}, "invalid patch file specification")
        original = path.read_bytes()
        require(digest(original) == entry["before"], "preimage hash drift")
        require(end > i, "empty file patch")
        updated = patched_bytes(original, lines[i:end])
        require(digest(updated) == entry["after"], "postimage hash drift")
        pending[name] = updated
        i = end
    require(
        bool(pending) and set(pending) == set(spec["files"]),
        "unexpected patch file set",
    )
    for name, data in pending.items():
        (Path(root) / name).write_bytes(data)
    expected = before["files"].copy()
    for name, data in pending.items():
        expected[name] = {**expected[name], "sha256": digest(data), "bytes": len(data)}
    actual = tree_manifest(root)
    require(actual["files"] == expected, "unexpected effective source changes")
    return actual


def verify_primary(root):
    files = tree_manifest(root)["files"]
    forbidden = (
        b"diagnostic-integration",
        b"backend_probe",
        b"perf391_network_evidence",
        b"browser-probe",
        b"diagnostic_app",
    )
    for name in files:
        if name.startswith(("backend/", "frontend/")) and name.endswith(
            (".py", ".ts", ".tsx", ".js", ".mjs", "Dockerfile", ".yml", ".yaml")
        ):
            data = (Path(root) / name).read_bytes()
            require(
                not any(token in data for token in forbidden),
                "diagnostic import in primary source",
            )


def manifest_template(
    role, integration_sha, ancestry_sha, archive_hash, patch_hash, effective_hash
):
    require(role in ("A", "C"), "unknown role")
    manifest = {
        "schema": SCHEMA,
        "version": 1,
        "role": role,
        "base_application_sha": PINS[role],
        "ancestry_sha": ancestry_sha,
        "implementation_reference_sha": PINS["implementation"],
        "integration_source_sha": integration_sha,
        "collector_source_sha": PINS["collector"],
        "collector_release_sha": PINS["release"],
        "frozen_harness_sha": PINS["harness"],
        "archive_sha256": archive_hash,
        "patch_sha256": patch_hash,
        "effective_source_sha256": effective_hash,
        "image_built": False,
        "image_digest": None,
        "compiled_assets": None,
        "labels": {},
    }
    manifest["labels"] = required_labels(manifest)
    validate_manifest(manifest)
    return manifest


def required_labels(manifest):
    return {
        "diagnostic": "true",
        "org.opencontainers.image.revision": manifest["base_application_sha"],
        **{
            k: manifest[k]
            for k in (
                "base_application_sha",
                "integration_source_sha",
                "collector_source_sha",
                "patch_sha256",
                "effective_source_sha256",
            )
        },
    }


def validate_manifest(manifest):
    from jsonschema import Draft202012Validator

    schema = json.loads(
        Path(__file__).with_name("build-manifest-schema.json").read_text()
    )
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    require(
        not errors, "invalid build manifest: " + "; ".join(e.message for e in errors)
    )
    require(
        manifest["base_application_sha"] == PINS[manifest["role"]],
        "wrong role base SHA",
    )
    for field, pin in (
        ("implementation_reference_sha", "implementation"),
        ("collector_source_sha", "collector"),
        ("collector_release_sha", "release"),
        ("frozen_harness_sha", "harness"),
    ):
        require(manifest[field] == PINS[pin], "wrong " + field)
    require(
        manifest["labels"] == required_labels(manifest),
        "missing/wrong diagnostic labels",
    )
