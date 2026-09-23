from pathlib import Path


BROWSER_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "acceptance/browser/v2-mission-retirement.mjs"
)


def test_browser_card_uses_required_cdp_window_protocol() -> None:
    source = BROWSER_SCRIPT.read_text(encoding="utf-8")

    assert "Browser.getWindowForTarget" in source
    assert "Browser.setContentsSize" in source
    assert "1920" in source and "1080" in source
    assert "Emulation.setDeviceMetricsOverride" not in source
    assert "@playwright/test" in source


def test_browser_card_requires_pre_and_post_neutral_metrics() -> None:
    source = BROWSER_SCRIPT.read_text(encoding="utf-8")

    assert source.count("assertExactViewport") >= 2
    assert "Create New Mission" in source
    assert "v2-activation-route.kml" in source


def test_browser_card_resolves_relative_log_paths_inside_evidence_directory() -> None:
    source = BROWSER_SCRIPT.read_text(encoding="utf-8")

    assert "resolve(root, target)" in source
