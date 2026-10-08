"""Delivered PDF words must cover assigned cells, not just selected phrases."""

import importlib
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest

FONTS = """name                                 type              encoding         emb sub uni object ID
------------------------------------ ----------------- ---------------- --- --- --- ---------
AAAAAA+DejaVuSans                     CID TrueType      Identity-H       yes yes yes      4  0
BAAAAA+DejaVuSans-Bold                CID TrueType      Identity-H       yes yes yes      5  0
"""


def verifier():
    name = "app.mission.exporter.customer_pdf"
    assert importlib.util.find_spec(name), "Actual PDF row verification contract absent"
    return importlib.import_module(name)


def expectations():
    return {
        "schemaVersion": 1,
        "pageCount": 1,
        "pageSizePt": [960, 540],
        "pages": [{"page": 1, "tableBodyBoundsPt": [10, 40, 950, 150]}],
        "rows": [
            {
                "legId": "leg",
                "rowId": "r1",
                "page": 1,
                "displayCells": ["10:00–10:15", "Takeoff SOF", "Ka", "Nominal"],
                "cellBoundsPt": [
                    [10, 40, 180, 65],
                    [180, 40, 500, 65],
                    [500, 40, 750, 65],
                    [750, 40, 950, 65],
                ],
            },
            {
                "legId": "leg",
                "rowId": "r2",
                "page": 1,
                "displayCells": [
                    "12:25:01–12:25:05",
                    "Ka unavailable",
                    "Starshield",
                    "Degraded",
                ],
                "cellBoundsPt": [
                    [10, 100, 180, 125],
                    [180, 100, 500, 125],
                    [500, 100, 750, 125],
                    [750, 100, 950, 125],
                ],
            },
        ],
    }


def xml(words=None, pages=1):
    words = words or [
        ("10:00–10:15", 20, 45, 150, 57),
        ("Takeoff", 190, 45, 250, 57),
        ("SOF", 260, 45, 300, 57),
        ("Ka", 510, 45, 540, 57),
        ("Nominal", 760, 45, 830, 57),
        ("12:25:01–12:25:05", 20, 105, 160, 117),
        ("Ka", 190, 105, 220, 117),
        ("unavailable", 230, 105, 320, 117),
        ("Starshield", 510, 105, 600, 117),
        ("Degraded", 760, 105, 840, 117),
    ]
    body = "".join(
        f'<word xMin="{a}" yMin="{b}" xMax="{c}" yMax="{d}">{text}</word>'
        for text, a, b, c, d in words
    )
    return (
        "<html><body>"
        + "".join(
            f'<page width="960" height="540"><flow><block><line>{body}</line></block></flow></page>'
            for _ in range(pages)
        )
        + "</body></html>"
    )


def test_all_actual_pdf_rows_and_cells_are_verified():
    result = verifier().verify_pdf_layout(xml(), expectations(), FONTS)
    assert result["verified"] is True
    assert [r["rowId"] for r in result["rows"]] == ["r1", "r2"]
    assert all(r["cellsMatched"] and r["inBounds"] for r in result["rows"])


@pytest.mark.parametrize(
    "damage",
    ["missing", "duplicate", "swapped", "wrong-cell", "off-page", "split", "extra-row"],
)
def test_actual_pdf_damage_cannot_be_satisfied_by_text_elsewhere(damage):
    tree = ET.fromstring(xml())
    line = tree.find(".//line")
    words = list(line)
    if damage == "missing":
        line.remove(words[5])
    elif damage == "duplicate":
        line.append(deepcopy(words[5]))
    elif damage == "swapped":
        words[3].text, words[8].text = words[8].text, words[3].text
    elif damage == "wrong-cell":
        words[8].set("xMin", "760")
        words[8].set("xMax", "830")
    elif damage == "off-page":
        words[8].set("xMax", "961")
    elif damage == "split":
        words[8].set("yMin", "535")
        words[8].set("yMax", "547")
    else:
        extra = deepcopy(words[3])
        extra.set("yMin", "80")
        extra.set("yMax", "92")
        line.append(extra)
    with pytest.raises(ValueError):
        verifier().verify_pdf_layout(
            ET.tostring(tree, encoding="unicode"), expectations(), FONTS
        )


def test_repeated_text_still_requires_each_assigned_row():
    expected = expectations()
    expected["rows"][1]["displayCells"] = expected["rows"][0]["displayCells"]
    with pytest.raises(ValueError):
        verifier().verify_pdf_layout(xml(), expected, FONTS)


def test_wrapped_cells_use_geometric_reading_order_and_nfc():
    expected = expectations()
    expected["rows"][0]["displayCells"][1] = "Café coordination"
    raw = (
        xml()
        .replace("Takeoff", "Cafe\u0301")
        .replace(">SOF<", ">coordination<")
        .replace(
            'xMin="260" yMin="45" xMax="300" yMax="57"',
            'xMin="190" yMin="57" xMax="300" yMax="64"',
        )
    )
    assert verifier().verify_pdf_layout(raw, expected, FONTS)["verified"]


@pytest.mark.parametrize(
    "alteration", ["seconds", "offset", "punctuation", "approximation"]
)
def test_pdf_normalization_preserves_exact_clock_semantics(alteration):
    expected = expectations()
    expected["rows"][1]["displayCells"][0] = {
        "seconds": "12:25–12:26",
        "offset": "12:25:01 EDT–12:25:05 EST",
        "punctuation": "12:25:01-12:25:05",
        "approximation": "≈ 12:25:01–12:25:05",
    }[alteration]
    with pytest.raises(ValueError):
        verifier().verify_pdf_layout(xml(), expected, FONTS)


def test_pdf_rows_must_be_on_the_assigned_page():
    expected = expectations()
    expected["rows"][1]["page"] = 2
    with pytest.raises(ValueError):
        verifier().verify_pdf_layout(xml(), expected, FONTS)


@pytest.mark.parametrize(
    "fonts",
    [
        FONTS.replace("yes yes yes", "no yes yes"),
        FONTS.replace("DejaVuSans-Bold", "UnexpectedFont"),
    ],
)
def test_unembedded_or_substituted_pdf_font_fails(fonts):
    with pytest.raises(ValueError):
        verifier().verify_pdf_layout(xml(), expectations(), fonts)


def test_every_pdf_page_geometry_is_checked():
    with pytest.raises(ValueError):
        verifier().verify_pdf_layout(
            xml().replace('width="960"', 'width="959"'), expectations(), FONTS
        )
