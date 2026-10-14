"""The shipped print derivative preserves the master and its color profile."""

import importlib.util
from hashlib import sha256
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def test_logo_derivative_is_png_and_preserves_master(tmp_path):
    master = ROOT / "app/mission/assets/APO Patch.jpg"
    derivative = ROOT / "app/mission/assets/apo-patch-briefing.png"
    original = sha256(master.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location(
        "resize_logo", ROOT / "scripts/resize-briefing-logo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "logo.png"
    module.resize_logo(master, output, 263)
    first = output.read_bytes()
    module.resize_logo(master, output, 263)
    assert output.read_bytes() == first == derivative.read_bytes()
    assert sha256(master.read_bytes()).hexdigest() == original
    with Image.open(master) as source, Image.open(derivative) as image:
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == (263, 263)
        assert image.info.get("icc_profile") == source.info.get("icc_profile")
