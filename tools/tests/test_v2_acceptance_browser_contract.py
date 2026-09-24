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
