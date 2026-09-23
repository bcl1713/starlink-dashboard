import hashlib
import json
import subprocess
from pathlib import Path

PROVISION_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "acceptance/browser/provision-v2-mission-retirement-chromium.mjs"
)


def make_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "mission-planner"
    metadata = project / "node_modules/playwright-core/browsers.json"
    browser_root = tmp_path / "browsers"
    provenance = tmp_path / "provenance.json"
    metadata.parent.mkdir(parents=True)
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


def test_verify_derives_locked_revision_and_records_exact_executable_provenance(
    tmp_path: Path,
) -> None:
    """Fails if verify accepts an unpinned revision, path, version, or hash."""
    project, browser_root, provenance = make_project(tmp_path)
    chrome = executable(browser_root)

    result = run_preflight(
        "--mode",
        "verify",
        "--project-dir",
        str(project),
        "--browser-root",
        str(browser_root),
        "--provenance-file",
        str(provenance),
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
    installer = tmp_path / "must-not-run.sh"
    installer.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    installer.chmod(0o755)

    result = run_preflight(
        "--mode",
        "provision",
        "--project-dir",
        str(project),
        "--browser-root",
        str(browser_root),
        "--provenance-file",
        str(provenance),
        "--installer-command-json",
        json.dumps([str(installer)]),
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["status"] == "passed"
    assert record["installer"] is None


def test_verify_rejects_a_version_that_only_contains_the_expected_token(
    tmp_path: Path,
) -> None:
    """Fails if a prefix match accepts a browser other than the locked version."""
    project, browser_root, provenance = make_project(tmp_path)
    chrome = executable(browser_root)
    chrome.write_text("#!/bin/sh\necho 'Google Chrome 1.2.3.40'\n", encoding="utf-8")

    result = run_preflight(
        "--mode",
        "verify",
        "--project-dir",
        str(project),
        "--browser-root",
        str(browser_root),
        "--provenance-file",
        str(provenance),
    )

    assert result.returncode == 1
    record = json.loads(result.stdout)
    assert record["status"] == "failed"
    assert "version mismatch" in record["error"]
    assert not provenance.exists()


def test_provision_uses_injected_installer_then_fails_closed_on_wrong_version(
    tmp_path: Path,
) -> None:
    """Fails if install skips verification or fixture commands cannot exercise it."""
    project, browser_root, provenance = make_project(tmp_path)
    installer = tmp_path / "fixture-installer.sh"
    installer.write_text(
        "#!/bin/sh\n"
        'mkdir -p "$PLAYWRIGHT_BROWSERS_PATH/chromium-999/chrome-linux64"\n'
        "printf '%s\\n' '#!/bin/sh' \"echo 'Google Chrome 0.0.0.0'\" "
        '> "$PLAYWRIGHT_BROWSERS_PATH/chromium-999/chrome-linux64/chrome"\n'
        'chmod +x "$PLAYWRIGHT_BROWSERS_PATH/chromium-999/chrome-linux64/chrome"\n',
        encoding="utf-8",
    )
    installer.chmod(0o755)

    result = run_preflight(
        "--mode",
        "provision",
        "--project-dir",
        str(project),
        "--browser-root",
        str(browser_root),
        "--provenance-file",
        str(provenance),
        "--installer-command-json",
        json.dumps([str(installer)]),
    )

    assert result.returncode == 1
    record = json.loads(result.stdout)
    assert record["status"] == "failed"
    assert "version mismatch" in record["error"]
    assert not provenance.exists()
