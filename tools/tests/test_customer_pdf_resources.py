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


def test_resource_qualification_rejects_oversized_duplicate_assets():
    import pytest
    from pypdf import PdfReader, PdfWriter
    from tests.unit.pdf_resource_fixtures import make_pdf_fragments

    spec = importlib.util.spec_from_file_location(
        "resource_checks", ROOT / "tools/acceptance/customer-briefing/pdf_resources.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, records = make_pdf_fragments()
    writer = PdfWriter()
    for record in records.values():
        writer.append(PdfReader(io.BytesIO(record["pdf"])))
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    with pytest.raises(ValueError, match="logo"):
        module.qualify_resources(
            output.getvalue(), {"render": {"maps": {}, "fit": {"pages": []}}}
        )


def test_resource_qualification_accepts_measured_distinct_maps_and_rejects_regressions():
    import copy
    import pytest
    from pypdf import PdfWriter
    from pypdf.generic import (
        DictionaryObject,
        NameObject,
        NumberObject,
        DecodedStreamObject,
    )

    spec = importlib.util.spec_from_file_location(
        "resource_checks", ROOT / "tools/acceptance/customer-briefing/pdf_resources.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    writer = PdfWriter()

    def image(width, height, pixel):
        value = DecodedStreamObject()
        value.set_data(bytes([pixel]) * width * height * 3)
        value.update(
            {
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(width),
                NameObject("/Height"): NumberObject(height),
                NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                NameObject("/BitsPerComponent"): NumberObject(8),
            }
        )
        return writer._add_object(value.flate_encode())

    logo = image(263, 263, 127)
    maps = [image(875, 844, n) for n in (10, 20, 30)]
    pages = []
    for number in range(1, 6):
        page = writer.add_blank_page(960, 540)
        xobjects = DictionaryObject({NameObject("/Logo"): logo})
        measurement = {"page": number, "legId": f"leg-{number}"}
        if number in (1, 3, 4):
            xobjects[NameObject("/Map")] = maps[(1, 3, 4).index(number)]
            measurement["mapPlacement"] = {"boundsPx": [10, 20, 290, 290]}
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/XObject"): xobjects}
        )
        pages.append(measurement)
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    evidence = {
        "render": {
            "maps": {
                f"leg-{n}": {"viewport": {"width": 875, "height": 844}}
                for n in (1, 3, 4)
            },
            "fit": {"pages": pages},
        }
    }
    proof = module.qualify_resources(
        output.getvalue(),
        evidence,
        fixture=True,
        baseline_bytes=len(output.getvalue()) + 100,
    )
    assert proof["pageCount"] == 5 and proof["savedBytes"] == 100
    assert len(proof["images"]) == 4
    wrong = copy.deepcopy(evidence)
    wrong["render"]["maps"]["leg-1"]["viewport"]["width"] = 1920
    with pytest.raises(ValueError, match="placement"):
        module.qualify_resources(output.getvalue(), wrong, fixture=True)
    with pytest.raises(ValueError, match="reduce"):
        module.qualify_resources(
            output.getvalue(),
            evidence,
            fixture=True,
            baseline_bytes=len(output.getvalue()),
        )


def test_inventory_follows_tiling_pattern_resources():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        DictionaryObject,
        NameObject,
        NumberObject,
        ArrayObject,
        DecodedStreamObject,
    )
    from tests.unit.pdf_resource_fixtures import make_pdf_fragments

    _, records = make_pdf_fragments()
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(records["a"]["pdf"])))
    for page in writer.pages:
        resources = page["/Resources"]
        pattern = DecodedStreamObject()
        pattern.set_data(b"/Nested Do")
        pattern.update(
            {
                NameObject("/Type"): NameObject("/Pattern"),
                NameObject("/PatternType"): NumberObject(1),
                NameObject("/PaintType"): NumberObject(1),
                NameObject("/TilingType"): NumberObject(1),
                NameObject("/XStep"): NumberObject(8),
                NameObject("/YStep"): NumberObject(8),
                NameObject("/BBox"): ArrayObject(
                    [NumberObject(v) for v in (0, 0, 8, 8)]
                ),
                NameObject("/Resources"): DictionaryObject(
                    {NameObject("/XObject"): resources["/XObject"]}
                ),
            }
        )
        del resources["/XObject"]
        resources[NameObject("/Pattern")] = DictionaryObject(
            {NameObject("/P1"): writer._add_object(pattern)}
        )
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    images = inventory()(output.getvalue())
    assert len(images) == 5
    assert all(image["pages"] == [1, 2] for image in images)
