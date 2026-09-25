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


def test_browser_card_requires_webgl2_preflight_identity() -> None:
    card = source()

    assert "webgl2Preflight" in card


def test_browser_card_rejects_direct_browser_launch_inputs() -> None:
    """Fails if this retired card can still create a browser outside the platform."""
    completed = subprocess.run(
        [
            "node",
            str(BROWSER_SCRIPT),
            "--mode",
            "neutral",
            "--chrome",
            "/bin/true",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 1
    assert "platform-owned browser session" in completed.stdout


def test_webgl2_preflight_fails_closed_for_missing_context_blank_and_overlong_values() -> (
    None
):
    """Fails if WebGL1/null/unsafe identity can produce a successful card result."""
    helper = (
        Path(__file__).resolve().parents[1] / "acceptance/browser/webgl2-preflight.mjs"
    )
    program = """
const { webgl2Preflight } = await import(process.argv[1]);
const scenario = process.argv[2];
const values = scenario === 'blank'
  ? { renderer: 'renderer', vendor: ' ', version: 'version' }
  : scenario === 'overlong'
    ? { renderer: 'x'.repeat(513), vendor: 'vendor', version: 'version' }
    : { renderer: 'renderer', vendor: 'vendor', version: 'version' };
global.document = { createElement: () => ({ getContext: (kind) => {
  if (scenario === 'webgl1') return kind === 'webgl' ? {} : null;
  if (scenario === 'null') return null;
  return {
    getExtension: () => null,
    RENDERER: 'renderer', VENDOR: 'vendor', VERSION: 'version',
    getParameter: (key) => values[key],
  };
} }) };
webgl2Preflight();
"""
    for scenario in ("webgl1", "null", "blank", "overlong"):
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", program, helper.as_uri(), scenario],
            capture_output=True,
            check=False,
            text=True,
        )
        assert completed.returncode != 0
        assert "platform WebGL2 preflight failed" in completed.stderr


def test_retired_browser_card_has_no_acceptance_capability() -> None:
    """The former standalone card must direct callers to the platform session."""
    card = source()

    assert "direct browser card is retired" in card
    assert "start(state, config.chrome" not in card


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


def test_retired_browser_card_does_not_claim_window_protocol_execution() -> None:
    """Viewport authority now belongs exclusively to the platform health card."""
    card = source()

    assert "direct browser card is retired" in card
    assert "setExactWindow(page, state, 'initial-window')" not in card


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


def test_v2_adapter_executes_bounded_exact_semantic_readiness_locators(
    tmp_path: Path,
) -> None:
    """Only exact named POI cells in two body rows can satisfy the executed waits."""
    repository = tmp_path / "repository"
    adapter = repository / "tools/acceptance/journeys/v2-mission-retirement.mjs"
    package = repository / "frontend/mission-planner/package.json"
    playwright = repository / "frontend/mission-planner/node_modules/@playwright/test"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(
        ADAPTER_SCRIPT.read_text(encoding="utf-8")
        + "\nexport { assertSemanticOverview };\n",
        encoding="utf-8",
    )
    package.parent.mkdir(parents=True)
    package.write_text('{"name":"semantic-readiness-test"}\n', encoding="utf-8")
    playwright.mkdir(parents=True)
    (playwright / "index.js").write_text("exports.chromium = {};\n", encoding="utf-8")
    program = r"""
const { assertSemanticOverview } = await import(process.argv[1]);
const timeout = 10_000;
class Locator {
  constructor(page, kind, rows = null, exact = null, root = null) { Object.assign(this, { page, kind, rows, exact, root }); }
  getByText(text, options = {}) {
    if (this.kind === 'legend') return new Locator(this.page, 'route', null, options.exact ? text : null);
    if (this.kind === 'cells') return new Locator(this.page, 'cells', null, options.exact ? text : null, this.root);
    throw new Error(`unexpected getByText on ${this.kind}`);
  }
  locator(selector) {
    if (this.kind === 'poi-panel' && selector === 'tbody tr') return new Locator(this.page, 'rows', this.page.rows);
    if (this.kind === 'page' && selector === 'td:nth-child(2)') return new Locator(this.page, 'cells', null, null, 'global');
    if (this.kind === 'rows' && selector === 'td:nth-child(2)') return new Locator(this.page, 'cells', null, null, 'rows');
    throw new Error(`unexpected locator ${this.kind} ${selector}`);
  }
  filter(options) {
    if (this.kind !== 'rows') throw new Error('filter must be scoped to body rows');
    if (options.has?.kind === 'cells' && options.has.root === 'global') return new Locator(this.page, 'rows', this.rows.filter((row) => row.name === options.has.exact));
    if (options.has?.kind === 'cells') throw new Error('has locator must be global, not rooted through candidate rows');
    if (options.hasText) return new Locator(this.page, 'rows', this.rows.filter((row) => row.name.includes(options.hasText)));
    if (options.hasNotText) return new Locator(this.page, 'rows', this.rows.filter((row) => !row.name.includes(options.hasNotText)));
    throw new Error('unexpected row filter');
  }
  first() { return new Locator(this.page, this.kind, this.rows?.slice(0, 1), this.exact, this.root); }
  nth(index) { return new Locator(this.page, this.kind, this.rows?.slice(index, index + 1), this.exact, this.root); }
  async waitFor(options) {
    this.page.waits.push({ kind: this.kind, exact: this.exact, rows: this.rows?.map((row) => row.name), options });
    const visible = this.kind === 'route' ? this.page.route === this.exact : this.rows?.length > 0;
    if (!visible) throw new Error('not visible');
  }
  async count() { return this.rows.length; }
  async innerText() { return this.kind === 'route' ? this.page.route : this.rows[0].name; }
}
const page = (route, rows) => ({
  route, rows, waits: [],
  getByLabel(name) { return new Locator(this, name === 'Globe legend' ? 'legend' : 'poi-panel'); },
  locator(selector) { return new Locator(this, 'page').locator(selector); },
  evaluate: async () => {},
});
for (const candidate of [
  page('V2 Acceptance Route KAAA-KBBB', []),
  page('V2 Acceptance Route KAAA-KBBB', [{ name: 'KAAA1' }, { name: 'prefix-KBBB' }]),
  page('V2 Acceptance Route KAAA-KBBB', [{ name: 'KAAA' }, { name: 'KAAA' }]),
]) {
  await assertSemanticOverview(candidate).then(
    () => { throw new Error('static, decoy, or non-distinct POI rows were accepted'); },
    () => {},
  );
}
const ready = page('V2 Acceptance Route KAAA-KBBB', [{ name: 'KAAA' }, { name: 'KBBB' }]);
const visible = await assertSemanticOverview(ready);
if (visible.poiRows !== 2 || visible.firstPoi !== 'KAAA' || visible.secondPoi !== 'KBBB') throw new Error('exact readiness result was not observed');
if (ready.waits.length !== 4 || ready.waits.some(({ options }) => options.state !== 'visible' || options.timeout !== timeout)) throw new Error('executed readiness waits are not bounded');
if (!ready.waits.some(({ kind, exact }) => kind === 'route' && exact === 'V2 Acceptance Route KAAA-KBBB')) throw new Error('route readiness was not scoped to the legend locator');
if (!ready.waits.some(({ kind, rows }) => kind === 'rows' && rows?.join(',') === 'KAAA')) throw new Error('KAAA exact body row was not waited');
if (!ready.waits.some(({ kind, rows }) => kind === 'rows' && rows?.join(',') === 'KBBB')) throw new Error('KBBB exact body row was not waited');
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", program, adapter.as_uri()],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


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


def test_production_adapter_rejects_png_with_corrupt_ihdr_crc(tmp_path: Path) -> None:
    """IHDR must be structurally authentic before its dimensions are trusted."""

    png = bytearray(_decoded_png(2))
    png[29] ^= 1
    completed = _run_production_png_parser(tmp_path, bytes(png))

    assert completed.returncode != 0
    assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_rejects_png_with_corrupt_chunk_crc(tmp_path: Path) -> None:
    """Every critical structural chunk is checksummed, not just IHDR."""

    for kind in (b"IHDR", b"IDAT", b"IEND"):
        png = bytearray(_decoded_png(2))
        cursor = 8
        while png[cursor + 4 : cursor + 8] != kind:
            cursor += 12 + struct.unpack(">I", png[cursor : cursor + 4])[0]
        length = struct.unpack(">I", png[cursor : cursor + 4])[0]
        png[cursor + 8 + length] ^= 1
        completed = _run_production_png_parser(tmp_path, bytes(png))

        assert completed.returncode != 0, kind
        assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_rejects_png_with_corrupt_ancillary_chunk_crc(tmp_path: Path) -> None:
    """CRC validation applies to ancillary chunks too."""

    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1920, 1080, 8, 2, 0, 0, 0))
    text = bytearray(_png_chunk(b"tEXt", b"source=platform"))
    text[-1] ^= 1
    idat = _png_chunk(b"IDAT", zlib.compress(b"\0" * (1080 * (1920 * 3 + 1))))
    completed = _run_production_png_parser(
        tmp_path, b"\x89PNG\r\n\x1a\n" + ihdr + bytes(text) + idat + _png_chunk(b"IEND", b"")
    )

    assert completed.returncode != 0
    assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_requires_ihdr_first_and_rejects_unknown_critical_chunks(
    tmp_path: Path,
) -> None:
    """Only recognized critical chunks may surround the IDAT stream."""

    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1920, 1080, 8, 2, 0, 0, 0))
    idat = _png_chunk(b"IDAT", zlib.compress(b"\0" * (1080 * (1920 * 3 + 1))))
    iend = _png_chunk(b"IEND", b"")
    for png in (
        b"\x89PNG\r\n\x1a\n" + _png_chunk(b"ABCD", b"") + ihdr + idat + iend,
        b"\x89PNG\r\n\x1a\n" + ihdr + idat + _png_chunk(b"ABCD", b"") + iend,
    ):
        completed = _run_production_png_parser(tmp_path, png)

        assert completed.returncode != 0
        assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_accepts_only_safe_rgb_plte_structure(tmp_path: Path) -> None:
    """The only additional known critical chunk is bounded to valid RGB placement."""

    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1920, 1080, 8, 2, 0, 0, 0))
    idat = _png_chunk(b"IDAT", zlib.compress(b"\0" * (1080 * (1920 * 3 + 1))))
    png = b"\x89PNG\r\n\x1a\n" + ihdr + _png_chunk(b"PLTE", b"\0\0\0") + idat + _png_chunk(b"IEND", b"")
    completed = _run_production_png_parser(tmp_path, png)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"width": 1920, "height": 1080}


def test_production_adapter_rejects_unsafe_plte_color_types_and_lengths(
    tmp_path: Path,
) -> None:
    """PLTE is limited to valid truecolor forms and 1–256 RGB entries."""

    signature = b"\x89PNG\r\n\x1a\n"
    rgba_ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1920, 1080, 8, 6, 0, 0, 0))
    rgba_idat = _png_chunk(b"IDAT", zlib.compress(b"\0" * (1080 * (1920 * 4 + 1))))
    valid_iend = _png_chunk(b"IEND", b"")
    invalid_palette_lengths = (b"", b"\0" * 4, b"\0" * 769)
    invalid_color_type = _png_chunk(
        b"IHDR", struct.pack(">IIBBBBB", 1920, 1080, 8, 3, 0, 0, 0)
    )
    inputs = [
        signature + rgba_ihdr + _png_chunk(b"PLTE", palette) + rgba_idat + valid_iend
        for palette in invalid_palette_lengths
    ] + [
        signature
        + invalid_color_type
        + _png_chunk(b"PLTE", b"\0\0\0")
        + _png_chunk(b"IDAT", zlib.compress(b"\0"))
        + valid_iend
    ]

    for png in inputs:
        completed = _run_production_png_parser(tmp_path, png)

        assert completed.returncode != 0
        assert "screenshot is not a decoded PNG" in completed.stderr


def test_production_adapter_accepts_valid_rgba_plte_viewport_screenshot(
    tmp_path: Path,
) -> None:
    """PLTE is optional, but valid, for truecolor-with-alpha PNGs."""

    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1920, 1080, 8, 6, 0, 0, 0))
    plte = _png_chunk(b"PLTE", b"\0\0\0")
    idat = _png_chunk(b"IDAT", zlib.compress(b"\0" * (1080 * (1920 * 4 + 1))))
    completed = _run_production_png_parser(
        tmp_path, b"\x89PNG\r\n\x1a\n" + ihdr + plte + idat + _png_chunk(b"IEND", b"")
    )

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
