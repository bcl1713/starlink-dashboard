# Task 4: Profile-owned ANGLE/SwiftShader WebGL2 preflight and final verification

Companion to
[2026-09-25-v2-upcoming-pois-webgl](2026-09-25-v2-upcoming-pois-webgl.md).

## Task 4: Profile-owned ANGLE/SwiftShader WebGL2 preflight

**Files:**

- Modify: `tools/acceptance/platform/browser_bundle.py:21-47`
- Modify: `tools/acceptance/platform/health.py:146-191, 410-430`
- Modify: `tools/acceptance/browser/v2-mission-retirement.mjs`
- Modify: `tools/tests/test_acceptance_platform_bundle.py`
- Modify: `tools/tests/test_acceptance_platform_health.py`
- Modify: `tools/tests/test_v2_acceptance_browser_contract.py`
- Modify: `docs/operations/acceptance-platform.md`

**Interfaces:**

- Consumes: descriptor-bound `BrowserLaunchSpec.start(*arguments)` and
  platform-owned health card output.

- Produces: final/health browser session launched with the two exact flags and a
  bounded `webgl2` result containing `renderer`, `vendor`, and `version`;
  failure blocks before Compose.

- [ ] **Step 1: Write failing browser-launch and neutral-card tests**

Add tests with a fake descriptor launcher and a health-card fixture:

```python
def test_platform_browser_launch_adds_only_certified_angle_swiftshader_flags(monkeypatch):
    launched_arguments: tuple[str, ...] = ()
    def capture_start(_: int, arguments: tuple[str, ...]):
        nonlocal launched_arguments
        launched_arguments = arguments
        return FakeProcess()
    monkeypatch.setattr(browser_bundle_module, "_start_descriptor", capture_start)
    BrowserLaunchSpec(os.open(fake_browser, os.O_RDONLY)).start("about:blank")
    assert launched_arguments[-3:] == (
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "about:blank",
    )
    assert "--enable-unsafe-swiftshader" not in launched_arguments


def test_final_browser_session_rejects_neutral_card_without_webgl2(profile, tmp_path, executor):
    executor.run_card = lambda launch, root: HealthProbeResult(
        metrics=EXACT_VIEWPORT_METRICS, artifacts={}, webgl2=None
    )
    with pytest.raises(ValueError, match="WebGL2"):
        start_final_browser_session(profile, tmp_path, executor)
```

Add an executable card-contract test requiring `canvas.getContext('webgl2')` and
nonempty renderer/vendor/version before the card reports success.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=tools python -m pytest -q tools/tests/test_acceptance_platform_bundle.py tools/tests/test_acceptance_platform_health.py tools/tests/test_v2_acceptance_browser_contract.py
```

Expected: launch-argument and missing-WebGL2 tests fail before the capability is
implemented.

- [ ] **Step 3: Implement profile-owned flags and strict card data**

Extend only the platform launch authority so every browser launched from
`start_final_browser_session` uses:

```python
"--use-gl=angle",
"--use-angle=swiftshader",
```

Do not allow the product contract, runner CLI, or adapter to supply flags.
Extend the neutral card JSON with a bounded WebGL result:

```js
const canvas = document.createElement('canvas');
const gl = canvas.getContext('webgl2');
if (!gl) throw new Error('platform WebGL2 preflight failed');
const debug = gl.getExtension('WEBGL_debug_renderer_info');
const webgl2 = {
  renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
  vendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
  version: gl.getParameter(gl.VERSION),
};
```

Validate nonempty string fields in Python before returning the session, retain
the result in health/final browser evidence, and preserve all existing neutral
viewport/raster validation.

- [ ] **Step 4: Run focused browser platform suite to verify GREEN**

Run:

```bash
PYTHONPATH=tools python -m pytest -q tools/tests/test_acceptance_platform_bundle.py tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_v2_acceptance_browser_contract.py
python -m compileall -q tools/acceptance/platform tools/tests
node --check tools/acceptance/browser/v2-mission-retirement.mjs
git diff --check
```

Expected: all focused tests, syntax, compilation, and whitespace checks pass.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/platform/browser_bundle.py tools/acceptance/platform/health.py tools/acceptance/browser/v2-mission-retirement.mjs tools/tests docs/operations/acceptance-platform.md
git commit -m "fix(acceptance): certify WebGL2 browser capability"
```

## Final Verification

- [ ] Run the complete focused platform suite after all tasks:

```bash
PYTHONPATH=tools python -m pytest -q tools/tests/test_acceptance_platform_bundle.py tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_contracts.py tools/tests/test_acceptance_platform_docs.py tools/tests/test_v2_acceptance_browser_contract.py
```

- [ ] Run backend target verification from its project environment:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_eta_projection.py tests/unit/test_overview_upcoming_pois.py
black --check app tests
ruff check app tests
```

- [ ] After independent task review and whole-branch review, push the exact SHA,
  run fresh health and static lanes, then issue exactly one authorized
  1800-second final lane. Require sealed WebGL2 renderer identity, exact
  viewport/raster, visible KAAA/KBBB POI rows, image identity, checksums, and
  cleanup before any final claim.

[Return to the main plan](2026-09-25-v2-upcoming-pois-webgl.md).
