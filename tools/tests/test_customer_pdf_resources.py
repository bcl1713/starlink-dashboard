"""Inspect reachable image semantics independently of the product optimizer."""

import importlib.util
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/starlink-location"))


def inventory():
    spec = importlib.util.spec_from_file_location(
        "pdf_inventory", ROOT / "tools/acceptance/customer-briefing/pdf_resources.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.image_inventory


def test_inventory_follows_nested_forms_and_resolves_profiles_masks_and_color_spaces():
    from pypdf import PdfReader, PdfWriter
    from tests.unit.pdf_resource_fixtures import make_pdf_fragments

    _, records = make_pdf_fragments()
    writer = PdfWriter()
    for r in records.values():
        writer.append(PdfReader(io.BytesIO(r["pdf"])))
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    images = inventory()(output.getvalue())
    assert len(images) == 15  # four nested images and one soft mask per leg
    assert len({i["objectId"] for i in images}) == 15
    assert all(i["width"] == 4 and i["height"] == 4 for i in images)
    groups = {}
    for image in images:
        groups.setdefault(image["semanticHash"], []).append(image)
    assert sorted(len(g) for g in groups.values()) == [1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3]
    assert all(i["encodedBytes"] > 0 and i["pages"] for i in images)
