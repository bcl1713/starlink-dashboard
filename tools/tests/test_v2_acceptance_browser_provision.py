import hashlib
import json
import os
import subprocess
from pathlib import Path

PROVISION_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "acceptance/browser/provision-v2-mission-retirement-chromium.mjs"
)
CARD_SCRIPT = (
    Path(__file__).resolve().parents[1] / "acceptance/browser/v2-mission-retirement.mjs"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MISSION_PLANNER = PROJECT_ROOT / "frontend/mission-planner"


def make_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "mission-planner"
    metadata = project / "node_modules/playwright-core/browsers.json"
    browser_root = tmp_path / "browsers"
    task_root = tmp_path / "task-owned"
    provenance = task_root / "provenance.json"
    metadata.parent.mkdir(parents=True)
    task_root.mkdir()
    (project / "package.json").write_text(
        json.dumps({"devDependencies": {"@playwright/test": "1.63.0"}}),
        encoding="utf-8",
    )
    (project / "package-lock.json").write_text(
        json.dumps(
            {
                "lockfileVersion": 3,
                "packages": {
                    "": {"devDependencies": {"@playwright/test": "1.63.0"}},
                    "node_modules/@playwright/test": {
                        "version": "1.63.0",
                        "integrity": "sha512-test",
                        "dependencies": {"playwright": "1.63.0"},
                    },
                    "node_modules/playwright": {
                        "version": "1.63.0",
                        "integrity": "sha512-playwright",
                        "dependencies": {"playwright-core": "1.63.0"},
                    },
                    "node_modules/playwright-core": {
                        "version": "1.63.0",
                        "integrity": "sha512-core",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (project / "node_modules/playwright-core/package.json").write_text(
        json.dumps({"version": "1.63.0"}), encoding="utf-8"
    )
    playwright_package = project / "node_modules/playwright/package.json"
    playwright_package.parent.mkdir()
    playwright_package.write_text(json.dumps({"version": "1.63.0"}), encoding="utf-8")
    metadata.write_text(
        json.dumps(
            {
                "browsers": [
                    {
                        "name": "chromium",
                        "revision": "999",
                        "browserVersion": "1.2.3.4",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    npm = project / "trusted-npm"
    npm.write_text(
        "#!/usr/bin/env node\n"
        "const args = process.argv.slice(2).join(' ');\n"
        "if (args === '--version') console.log('10.9.0');\n"
        "else if (args !== 'ci --ignore-scripts') process.exit(64);\n",
        encoding="utf-8",
    )
    npm.chmod(0o755)
    return project, browser_root, provenance


def executable(browser_root: Path) -> Path:
    chrome = browser_root / "chromium-999/chrome-linux64/chrome"
    chrome.parent.mkdir(parents=True)
    chrome.write_text("#!/bin/sh\necho 'Google Chrome 1.2.3.4'\n", encoding="utf-8")
    chrome.chmod(0o755)
    return chrome


def run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(PROVISION_SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def preflight_args(project: Path, browser_root: Path, provenance: Path) -> list[str]:
    return [
        "--project-dir",
        str(project),
        "--browser-root",
        str(browser_root),
        "--task-root",
        str(provenance.parent),
        "--provenance-file",
        str(provenance),
        "--npm-executable",
        str(project / "trusted-npm"),
    ]


def test_verify_derives_locked_revision_and_records_exact_executable_provenance(
    tmp_path: Path,
) -> None:
    """Fails if verify accepts an unpinned revision, path, version, or hash."""
    project, browser_root, provenance = make_project(tmp_path)
    chrome = executable(browser_root)

    result = run_preflight(
        "--mode", "verify", *preflight_args(project, browser_root, provenance)
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["status"] == "passed"
    assert record["playwright"]["version"] == "1.63.0"
    assert record["chromium"]["revision"] == "999"
    assert record["chromium"]["version"] == "1.2.3.4"
    assert record["chromium"]["metadataSha256"]
    assert record["executable"]["path"] == str(chrome)
    assert (
        record["executable"]["sha256"]
        == hashlib.sha256(chrome.read_bytes()).hexdigest()
    )
    assert json.loads(provenance.read_text(encoding="utf-8")) == record


def test_provision_is_idempotent_when_the_locked_executable_already_verifies(
    tmp_path: Path,
) -> None:
    """Fails if provision downloads despite a matching pinned browser."""
    project, browser_root, provenance = make_project(tmp_path)
    executable(browser_root)

    result = run_preflight(
        "--mode", "provision", *preflight_args(project, browser_root, provenance)
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["installer"] is None


def test_verify_rejects_a_version_that_only_contains_the_expected_token(
    tmp_path: Path,
) -> None:
    """Fails if a prefix match accepts a browser other than the locked version."""
    project, browser_root, provenance = make_project(tmp_path)
    chrome = executable(browser_root)
    chrome.write_text("#!/bin/sh\necho 'Google Chrome 1.2.3.40'\n", encoding="utf-8")

    result = run_preflight(
        "--mode", "verify", *preflight_args(project, browser_root, provenance)
    )

    assert result.returncode == 1
    assert "version mismatch" in json.loads(result.stdout)["error"]
    assert not provenance.exists()


def test_production_cli_rejects_arbitrary_installer_override(tmp_path: Path) -> None:
    """Fails if callers can replace the pinned local Playwright installer."""
    project, browser_root, provenance = make_project(tmp_path)
    executable(browser_root)

    result = run_preflight(
        "--mode",
        "verify",
        *preflight_args(project, browser_root, provenance),
        "--installer-command-json",
        json.dumps(["/bin/false"]),
    )

    assert result.returncode == 1
    assert "invalid argument" in json.loads(result.stdout)["error"]
    assert not provenance.exists()


def test_verify_rejects_installed_playwright_core_version_mismatch_before_metadata(
    tmp_path: Path,
) -> None:
    """Fails if browsers metadata is trusted from a different installed core."""
    project, browser_root, provenance = make_project(tmp_path)
    executable(browser_root)
    (project / "node_modules/playwright-core/package.json").write_text(
        json.dumps({"version": "1.63.1"}), encoding="utf-8"
    )
    (project / "node_modules/playwright-core/browsers.json").write_text(
        "not-json", encoding="utf-8"
    )

    result = run_preflight(
        "--mode", "verify", *preflight_args(project, browser_root, provenance)
    )

    assert result.returncode == 1
    assert (
        "installed playwright-core version does not match package-lock"
        in json.loads(result.stdout)["error"]
    )
    assert not provenance.exists()


def test_invalid_input_preserves_prior_provenance_until_atomic_success_replacement(
    tmp_path: Path,
) -> None:
    """Fails if validation deletes a prior record before a replacement is ready."""
    project, browser_root, provenance = make_project(tmp_path)
    executable(browser_root)
    prior = '{"status":"passed","prior":true}\n'
    provenance.write_text(prior, encoding="utf-8")
    (project / "node_modules/playwright-core/package.json").write_text(
        json.dumps({"version": "0.0.0"}), encoding="utf-8"
    )

    failed = run_preflight(
        "--mode", "verify", *preflight_args(project, browser_root, provenance)
    )
    assert failed.returncode == 1
    assert provenance.read_text(encoding="utf-8") == prior

    (project / "node_modules/playwright-core/package.json").write_text(
        json.dumps({"version": "1.63.0"}), encoding="utf-8"
    )
    passed = run_preflight(
        "--mode", "verify", *preflight_args(project, browser_root, provenance)
    )
    assert passed.returncode == 0
    assert json.loads(provenance.read_text(encoding="utf-8"))["status"] == "passed"


def test_verify_rejects_installed_playwright_version_mismatch_before_metadata(
    tmp_path: Path,
) -> None:
    """Fails if a substituted installed Playwright package is trusted."""
    project, browser_root, provenance = make_project(tmp_path)
    executable(browser_root)
    package_path = project / "node_modules/playwright/package.json"
    package_path.write_text(json.dumps({"version": "1.63.1"}), encoding="utf-8")
    (project / "node_modules/playwright-core/browsers.json").write_text(
        "not-json", encoding="utf-8"
    )

    result = run_preflight(
        "--mode", "verify", *preflight_args(project, browser_root, provenance)
    )

    assert result.returncode == 1
    assert (
        "installed playwright version does not match package-lock"
        in json.loads(result.stdout)["error"]
    )
    assert not provenance.exists()


def test_provision_rejects_symlinked_local_playwright_cli_before_invocation(
    tmp_path: Path,
) -> None:
    """Fails if the installer entrypoint resolves outside locked node_modules."""
    project, browser_root, provenance = make_project(tmp_path)
    package_path = project / "node_modules/playwright/package.json"
    package_path.write_text(json.dumps({"version": "1.63.0"}), encoding="utf-8")
    substitute = tmp_path / "substitute-cli.js"
    substitute.write_text("process.exit(99);\n", encoding="utf-8")
    os.symlink(substitute, project / "node_modules/playwright/cli.js")

    result = run_preflight(
        "--mode", "provision", *preflight_args(project, browser_root, provenance)
    )

    assert result.returncode == 1
    assert (
        "Playwright CLI must be a non-symlink regular file"
        in json.loads(result.stdout)["error"]
    )
    assert not provenance.exists()


def test_provision_replaces_a_regular_file_cli_before_installer_execution(
    tmp_path: Path,
) -> None:
    """Fails if a regular-file CLI substitute can run instead of npm-ci output."""
    project, browser_root, provenance = make_project(tmp_path)
    cli = project / "node_modules/playwright/cli.js"
    cli.write_text(
        "require('node:fs').writeFileSync(process.env.MALICIOUS_MARKER, 'ran');\n",
        encoding="utf-8",
    )
    marker = tmp_path / "malicious-ran"
    npm_log = tmp_path / "npm-command.json"
    fake_npm = project / "trusted-npm"
    fake_npm.write_text(
        "#!/usr/bin/env node\n"
        "const fs = require('node:fs');\n"
        "const path = require('node:path');\n"
        "const args = process.argv.slice(2).join(' ');\n"
        "if (args === '--version') console.log('10.9.0');\n"
        "else if (args === 'ci --ignore-scripts') { fs.writeFileSync(process.env.NPM_LOG, JSON.stringify({argv: process.argv.slice(2), cwd: process.cwd()})); fs.writeFileSync(path.join(process.cwd(), 'node_modules/playwright/cli.js'), `const fs = require('node:fs'); const path = require('node:path'); const root = process.env.PLAYWRIGHT_BROWSERS_PATH; const chrome = path.join(root, 'chromium-999/chrome-linux64/chrome'); fs.mkdirSync(path.dirname(chrome), {recursive: true}); fs.writeFileSync(chrome, \"#!/bin/sh\\\\necho 'Google Chrome 1.2.3.4'\\\\n\"); fs.chmodSync(chrome, 0o755);`); } else process.exit(64);\n",
        encoding="utf-8",
    )
    fake_npm.chmod(0o755)

    result = subprocess.run(
        [
            "node",
            str(PROVISION_SCRIPT),
            "--mode",
            "provision",
            *preflight_args(project, browser_root, provenance),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "NPM_LOG": str(npm_log),
            "MALICIOUS_MARKER": str(marker),
        },
    )

    assert result.returncode == 0, result.stdout
    assert json.loads(npm_log.read_text(encoding="utf-8")) == {
        "argv": ["ci", "--ignore-scripts"],
        "cwd": str(project),
    }
    record = json.loads(result.stdout)
    assert record["packagePreparation"] == {
        "command": [str(fake_npm), "ci", "--ignore-scripts"],
        "executable": {
            "path": str(fake_npm),
            "sha256": hashlib.sha256(fake_npm.read_bytes()).hexdigest(),
            "size": fake_npm.stat().st_size,
            "versionOutput": "10.9.0",
        },
        "lockfileSha256": hashlib.sha256(
            (project / "package-lock.json").read_bytes()
        ).hexdigest(),
        "stdout": "",
        "stderr": "",
    }
    assert not marker.exists()
    assert record["installer"]["command"][1] == str(cli)


def test_provision_rejects_successful_npm_that_keeps_malicious_cli(
    tmp_path: Path,
) -> None:
    """Fails closed before CLI execution when npm claims success without cleaning it."""
    project, browser_root, provenance = make_project(tmp_path)
    cli = project / "node_modules/playwright/cli.js"
    cli.write_text(
        "require('node:fs').writeFileSync(process.env.MALICIOUS_MARKER, 'ran');\n",
        encoding="utf-8",
    )
    marker = tmp_path / "malicious-ran"
    fake_npm = project / "trusted-npm"
    fake_npm.write_text(
        "#!/usr/bin/env node\n"
        "const args = process.argv.slice(2).join(' ');\n"
        "if (args === '--version') console.log('10.9.0');\n"
        "else if (args !== 'ci --ignore-scripts') process.exit(64);\n",
        encoding="utf-8",
    )
    fake_npm.chmod(0o755)

    result = subprocess.run(
        [
            "node",
            str(PROVISION_SCRIPT),
            "--mode",
            "provision",
            *preflight_args(project, browser_root, provenance),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "MALICIOUS_MARKER": str(marker),
        },
    )

    assert result.returncode == 1
    assert "did not replace Playwright CLI" in json.loads(result.stdout)["error"]
    assert not marker.exists()
    assert not provenance.exists()


def test_provenance_rejects_task_root_escape_and_symlinked_parent(
    tmp_path: Path,
) -> None:
    """Fails if provenance can be written outside the explicitly task-owned root."""
    project, browser_root, provenance = make_project(tmp_path)
    executable(browser_root)
    escaped = tmp_path / "outside.json"
    escaped_result = run_preflight(
        "--mode",
        "verify",
        "--project-dir",
        str(project),
        "--browser-root",
        str(browser_root),
        "--task-root",
        str(provenance.parent),
        "--provenance-file",
        str(escaped),
    )
    assert escaped_result.returncode == 1
    assert (
        "path escapes its required root" in json.loads(escaped_result.stdout)["error"]
    )
    assert not escaped.exists()

    external = tmp_path / "external"
    external.mkdir()
    linked_parent = provenance.parent / "linked"
    os.symlink(external, linked_parent)
    linked_provenance = linked_parent / "provenance.json"
    linked_result = run_preflight(
        "--mode", "verify", *preflight_args(project, browser_root, linked_provenance)
    )
    assert linked_result.returncode == 1
    assert "symlink" in json.loads(linked_result.stdout)["error"]
    assert not (external / "provenance.json").exists()


def test_browser_card_rejects_each_stale_provenance_identity_field(
    tmp_path: Path,
) -> None:
    """Fails if a provenance record survives project/lock/metadata/version/hash drift."""
    package = json.loads((MISSION_PLANNER / "package.json").read_text(encoding="utf-8"))
    lock_path = MISSION_PLANNER / "package-lock.json"
    metadata_path = MISSION_PLANNER / "node_modules/playwright-core/browsers.json"
    core_path = MISSION_PLANNER / "node_modules/playwright-core/package.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    chromium = next(item for item in metadata["browsers"] if item["name"] == "chromium")
    chrome = tmp_path / "fake-chrome"
    chrome.write_text("not a browser", encoding="utf-8")
    chrome.chmod(0o755)
    base = {
        "status": "passed",
        "taskRoot": str(tmp_path),
        "projectDir": str(MISSION_PLANNER),
        "lockfile": {
            "path": str(lock_path),
            "sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        },
        "playwright": {
            "version": package["devDependencies"]["@playwright/test"],
            "installedCoreVersion": json.loads(core_path.read_text(encoding="utf-8"))[
                "version"
            ],
        },
        "chromium": {
            "revision": chromium["revision"],
            "version": chromium["browserVersion"],
            "metadataPath": str(metadata_path),
            "metadataSha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        },
        "executable": {
            "path": str(chrome),
            "sha256": hashlib.sha256(chrome.read_bytes()).hexdigest(),
        },
    }
    cases = [
        (("projectDir",), "other-project", "current project"),
        (("lockfile", "sha256"), "0" * 64, "current package-lock"),
        (("chromium", "metadataSha256"), "0" * 64, "current Playwright metadata"),
        (("playwright", "version"), "0.0.0", "Playwright version"),
        (("chromium", "revision"), "0", "Chromium identity"),
        (("chromium", "version"), "0.0.0.0", "Chromium identity"),
        (("executable", "sha256"), "0" * 64, "checksum mismatch"),
    ]
    for index, (path, value, error) in enumerate(cases):
        record = json.loads(json.dumps(base))
        target = record
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        provenance = tmp_path / f"provenance-{index}.json"
        provenance.write_text(json.dumps(record), encoding="utf-8")
        result = subprocess.run(
            [
                "node",
                str(CARD_SCRIPT),
                "--mode",
                "neutral",
                "--chrome",
                str(chrome),
                "--display",
                ":97",
                "--cdp-port",
                str(19970 + index),
                "--profile-dir",
                str(tmp_path / f"profile-{index}"),
                "--evidence-dir",
                str(tmp_path / f"evidence-{index}"),
                "--task-root",
                str(tmp_path),
                "--provisioning-provenance",
                str(provenance),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert error in json.loads(result.stdout)["error"]
