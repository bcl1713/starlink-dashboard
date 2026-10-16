"""Inspect the delivered production PDF: independent text/cells and vector outlines."""

import json
import runpy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from pdf_geometry import verify_markers
from pypdf import PdfReader

# Reuse canonical full-cell, page-overflow, PDF resource and 240-DPI raster checks.
runpy.run_path("/acceptance/production_pdf_probe.py", run_name="__main__")
root = Path(sys.argv[2])
evidence = json.loads((root / "mission-customer-briefing-evidence.json").read_text())
pdf_path = next(root.glob("*.pdf"))
reader = PdfReader(pdf_path)
markers = []
for page_number, page in enumerate(reader.pages, 1):
    color = [0, 0, 0]
    stack = []
    candidates = []

    def visit(operator, operands, cm, _tm, stack=stack, candidates=candidates):
        global color
        if operator == b"q":
            stack.append(color[:])
        elif operator == b"Q" and stack:
            color = stack.pop()
        elif operator == b"RG":
            color = list(map(float, operands))
        elif operator == b"re" and all(
            abs(a - b) < 0.015 for a, b in zip(color, [0.451, 0.318, 0.141])
        ):
            x, y, width, height = map(float, operands)
            a, b, c, d, e, f = map(float, cm)
            corners = [
                (a * px + c * py + e, b * px + d * py + f)
                for px, py in [(x, y), (x + width, y + height)]
            ]
            xs, ys = zip(*corners)
            candidates.append([min(xs), 540 - max(ys), max(xs), 540 - min(ys)])

    page.extract_text(visitor_operand_before=visit)
    # The tiny legend outline is outside the row and has a different height.
    outlines = [box for box in candidates if 15 <= box[3] - box[1] <= 18]
    for box in outlines:
        assert 0 <= box[0] < box[2] <= 960 and 0 <= box[1] < box[3] <= 540, box
    markers.append({"page": page_number, "outlinesPt": outlines})

import subprocess

text = subprocess.check_output(
    ["pdftotext", "-bbox-layout", str(pdf_path), "-"], text=True, timeout=30
)
xml = ET.fromstring(text)
pages = [element for element in xml.iter() if element.tag.endswith("}page")]
for page, marker in zip(pages, markers):
    for word in page.iter():
        if not word.tag.endswith("}word") or "PoP" not in (word.text or ""):
            continue
        low, high = float(word.attrib["yMin"]), float(word.attrib["yMax"])
        assert not any(
            low < box[3] and high > box[1] for box in marker["outlinesPt"]
        ), "PoP text added inside timeline row"

forecasts = [leg["canonical"]["popForecast"] for leg in evidence["legs"]]
legs = {leg["legId"]: leg for leg in evidence["legs"]}
for index, page in enumerate(evidence["pages"]):
    canonical = legs[page["legId"]]["canonical"]
    # Continuation pages carry measured whole rows, with no duplicated timeline.
    if markers[index]["outlinesPt"]:
        markers[index]["canonicalAlignment"] = verify_markers(
            markers[index]["outlinesPt"],
            canonical["popForecast"],
            canonical["utcBounds"],
        )
expected = sum(len(forecast["transitions"]) for forecast in forecasts if forecast)
actual = sum(len(page["outlinesPt"]) for page in markers)
assert actual >= expected, ("Missing PDF outline markers", expected, markers)
if expected:
    assert "typically" in text, "Missing advisory explanatory note"
proof = {
    "markers": markers,
    "expectedTransitions": expected,
    "actualOutlineCount": actual,
    "noTimelinePopLabels": True,
    "allCanonicalCellsVerified": True,
    "snapshotFingerprint": evidence["snapshotFingerprint"],
    "catalogFingerprints": [
        forecast["catalog_fingerprint"] for forecast in forecasts if forecast
    ],
    "pageCount": len(reader.pages),
}
(root / "pop-pdf-proof.json").write_text(json.dumps(proof, indent=2))
print(json.dumps(proof))
