import os
import json
import struct
import subprocess
import zlib
from pathlib import Path

BROWSER_SCRIPT = (
    Path(__file__).resolve().parents[1] / "acceptance/browser/v2-mission-retirement.mjs"
)
ADAPTER_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "acceptance/journeys/v2-mission-retirement.mjs"
)


def source() -> str:
    return BROWSER_SCRIPT.read_text(encoding="utf-8")


def adapter_source() -> str:
    return ADAPTER_SCRIPT.read_text(encoding="utf-8")


def test_browser_card_uses_required_cdp_window_protocol() -> None:
    card = source()

    assert "Browser.getWindowForTarget" in card
    assert "Browser.setContentsSize" in card
    assert "Browser.getWindowBounds" in card
    assert "1920" in card and "1080" in card
    assert "Emulation.setDeviceMetricsOverride" not in card
    assert "@playwright/test" in card


def test_browser_card_requires_matching_provisioned_executable_provenance() -> None:
    """Fails if acceptance can silently consume an unprovisioned cache executable."""
    card = source()

    assert "provisioning-provenance" in card
    assert "config.provisioningProvenance" in card
    assert "provisioning.status !== 'passed'" in card
    assert "provisioning.executable?.path !== config.chrome" in card
    assert "provisioned executable checksum mismatch" in card


def test_browser_card_binds_provenance_to_current_locked_project_identity() -> None:
    """Fails if a passing record from another lock, metadata, or revision is reused."""
    card = source()

    for token in [
        "package-lock.json",
        "node_modules/playwright-core/browsers.json",
        "node_modules/playwright-core/package.json",
        "provisioning.projectDir !== projectDir",
        "provisioning.lockfile?.sha256 !== sha256(lockBytes)",
        "provisioning.chromium?.metadataSha256 !== sha256(metadataBytes)",
        "provisioning.playwright?.version !== declared",
        "provisioning.chromium?.revision !== chromium.revision",
        "provisioning.chromium?.version !== chromium.browserVersion",
        "installed playwright-core version does not match package-lock",
    ]:
        assert token in card


def test_browser_card_requires_task_root_bound_provenance_containment() -> None:
    """Fails if a valid record can be read from outside its task-owned root."""
    card = source()

    for token in [
        "taskRoot: resolve(value('task-root'))",
        "trustedProvenancePath(config.taskRoot, config.provisioningProvenance)",
        "provisioning.taskRoot !== config.taskRoot",
        "provisioning provenance task root does not match current task root",
    ]:
        assert token in card


def test_browser_card_checks_core_version_before_parsing_browsers_metadata() -> None:
    """Fails if malformed metadata masks a substituted installed core package."""
    card = source()

    assert card.index("installedCore.version !== corePackage.version") < card.index(
        "JSON.parse(metadataBytes.toString('utf8'))"
    )


def test_browser_card_polls_both_owned_children_and_records_listener_after_probe() -> (
    None
):
    """Fails if Xvfb can die silently or spawn time masquerades as readiness."""
    card = source()

    assert "waitForCdp(state, chrome, xvfb)" in card
    assert "Xvfb exited before CDP readiness" in card
    assert "firstListenerMs ??= Date.now() - state.startedAt" in card
    assert "state.probes.firstListenerMs = Date.now() - state.startedAt" not in card
    assert card.index("firstListenerMs ??=") > card.index(
        "const version = await fetchVersion"
    )
    assert "120_000" in card


def test_browser_card_reapplies_and_retains_window_protocol_after_each_mode() -> None:
    """Fails if final viewport evidence lacks a post-action native window record."""
    card = source()

    assert "setExactWindow(page, state, 'initial-window')" in card
    assert "setExactWindow(page, state, 'neutral-post-window')" in card
    assert "setExactWindow(page, state, 'journey-post-window')" in card
    assert card.index("neutral-post-window") < card.index("'neutral-post'")
    assert card.index("journey-post-window") < card.index("'journey-post'")


def test_browser_card_bounds_and_redacts_retained_page_evidence() -> None:
    """Fails if query-bearing or oversized console/network/DOM data is retained."""
    card = source()

    assert "MAX_ARTIFACT_BYTES" in card
    assert "MAX_RECORD_TEXT_BYTES" in card
    assert "redactUrl" in card
    assert "truncateText" in card
    assert "url.search = ''" in card
    assert "url.hash = ''" in card
    assert "truncateText(redactUrl(response.url()))" in card
    assert "truncateText(message.text())" in card
    assert "truncateText(await page.locator('main').innerText())" in card
    assert "artifact exceeds byte budget" in card


def test_browser_card_detaches_sessions_and_page_listeners_on_journey_failure() -> None:
    """Fails if an exception leaks a CDP session or page evidence listeners."""
    card = source()

    assert "await session.detach().catch(() => {})" in card
    assert "page.off('console', onConsole)" in card
    assert "page.off('response', onResponse)" in card
    assert "finally {\n    page.off('console', onConsole)" in card


def test_browser_card_requires_pre_and_post_neutral_metrics_and_journey_assets() -> (
    None
):
    card = source()

    assert card.count("assertExactViewport") >= 2
    assert "Create New Mission" in card
    assert "v2-activation-route.kml" in card


def test_adapter_cli_disposes_cdp_attachment_before_explicit_nonzero_exit() -> None:
    card = adapter_source()

    assert "let browser;" in card
    assert "finally {\n    await browser?.close().catch(() => {});" in card
    assert "process.stderr.write" in card
    assert "() => process.exit(1)," in card
    assert card.index("process.stderr.write") < card.index("() => process.exit(1),")


def test_production_adapter_closes_real_attachment_before_failure_exit(
    tmp_path: Path,
) -> None:
    """The shipped executable must release a live CDP attachment before exiting."""
    repository = tmp_path / "repository"
    adapter = repository / "tools/acceptance/journeys/v2-mission-retirement.mjs"
    package = repository / "frontend/mission-planner/package.json"
    playwright = repository / "frontend/mission-planner/node_modules/@playwright/test"
    closed = tmp_path / "adapter-closed"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(ADAPTER_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    package.parent.mkdir(parents=True)
    package.write_text('{"name":"production-adapter-lifecycle"}\n', encoding="utf-8")
    playwright.mkdir(parents=True)
    (playwright / "index.js").write_text(
        """const { writeFileSync } = require('node:fs');
const handle = setInterval(() => {}, 1_000);
exports.chromium = { connectOverCDP: async () => ({
  contexts: () => [],
  close: async () => { writeFileSync(process.env.ADAPTER_CLOSED, 'closed'); clearInterval(handle); },
}) };
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "node",
            str(adapter),
            "--repository-root",
            str(repository),
            "--session",
            "http://127.0.0.1:9222",
            "--origin",
            "http://127.0.0.1:5173",
            "--kml",
            str(tmp_path / "fixture.kml"),
        ],
        capture_output=True,
        check=False,
        env={**os.environ, "ADAPTER_CLOSED": str(closed)},
        text=True,
        timeout=3,
    )

    assert completed.returncode == 1
    assert "platform-supplied browser session has no context" in completed.stderr
    assert closed.read_text(encoding="utf-8") == "closed"


def _png_chunk(kind: bytes, content: bytes) -> bytes:
    return (
        struct.pack(">I", len(content))
        + kind
        + content
        + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
    )


def _decoded_png(
    color_type: int,
    raw: bytes | None = None,
    width: int = 1920,
    height: int = 1080,
) -> bytes:
    """Build a valid 8-bit PNG with decoded scanlines for its color type."""

    channels = {2: 3, 6: 4}[color_type]
    scanlines = raw if raw is not None else b"\0" * (height * (width * channels + 1))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(scanlines))
        + _png_chunk(b"IEND", b"")
    )


def _run_production_png_parser(tmp_path: Path, png: bytes) -> subprocess.CompletedProcess[str]:
    """Execute the shipped ESM parser, exposing only its otherwise-private helper."""

    repository = tmp_path / "repository"
    adapter = repository / "tools/acceptance/journeys/v2-mission-retirement.mjs"
    package = repository / "frontend/mission-planner/package.json"
    playwright = repository / "frontend/mission-planner/node_modules/@playwright/test"
    png_path = tmp_path / "screenshot.png"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(
        ADAPTER_SCRIPT.read_text(encoding="utf-8") + "\nexport { pngDimensions };\n",
        encoding="utf-8",
    )
    package.parent.mkdir(parents=True, exist_ok=True)
    package.write_text('{"name":"png-parser-test"}\n', encoding="utf-8")
    playwright.mkdir(parents=True, exist_ok=True)
    (playwright / "index.js").write_text("exports.chromium = {};\n", encoding="utf-8")
    png_path.write_bytes(png)
    return subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            (
                "import { readFileSync } from 'node:fs';"
                f"import {{ pngDimensions }} from {json.dumps(adapter.as_uri())};"
                "process.stdout.write(JSON.stringify(await pngDimensions(readFileSync(process.argv[1]))));"
            ),
            str(png_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_production_adapter_accepts_valid_opaque_rgb_viewport_screenshot(
    tmp_path: Path,
) -> None:
    """A fully decoded color-type-2 headed screenshot reaches the artifact raster path."""

    completed = _run_production_png_parser(tmp_path, _decoded_png(2))

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"width": 1920, "height": 1080}


def test_production_adapter_retains_rgba_viewport_screenshot_validation(
    tmp_path: Path,
) -> None:
    completed = _run_production_png_parser(tmp_path, _decoded_png(6))

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"width": 1920, "height": 1080}


def test_production_adapter_rejects_unsupported_png_color_types(tmp_path: Path) -> None:
    for color_type in (0, 3, 4):
        png = (
            b"\x89PNG\r\n\x1a\n"
            + _png_chunk(
                b"IHDR", struct.pack(">IIBBBBB", 1920, 1080, 8, color_type, 0, 0, 0)
            )
            + _png_chunk(b"IDAT", zlib.compress(b"\0"))
            + _png_chunk(b"IEND", b"")
        )
        completed = _run_production_png_parser(tmp_path, png)

        assert completed.returncode != 0
        assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_rejects_invalid_decoded_length_for_rgb_and_rgba(
    tmp_path: Path,
) -> None:
    for color_type in (2, 6):
        channels = {2: 3, 6: 4}[color_type]
        invalid_scanlines = b"\0" * (1080 * (1920 * channels + 1) - 1)
        completed = _run_production_png_parser(
            tmp_path, _decoded_png(color_type, invalid_scanlines)
        )

        assert completed.returncode != 0
        assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_rejects_pngs_over_twelve_mebibytes(tmp_path: Path) -> None:
    completed = _run_production_png_parser(tmp_path, b"\x89PNG\r\n\x1a\n" + b"x" * (12 * 1024 * 1024))

    assert completed.returncode != 0
    assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_rejects_non_exact_viewport_dimensions(tmp_path: Path) -> None:
    completed = _run_production_png_parser(tmp_path, _decoded_png(2, width=1919))

    assert completed.returncode != 0
    assert "screenshot is not a decoded PNG" in completed.stderr
