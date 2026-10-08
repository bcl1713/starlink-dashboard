"""Independent actual-PDF cell verification; no browser or fixture dependency."""

import argparse
import json
import math
import os
import re
import signal
import subprocess
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

SIZE = (960, 540)
TOLERANCE = 0.75


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def rectangle(value):
    if len(value) != 4 or any(
        not isinstance(v, (int, float)) or not math.isfinite(v) for v in value
    ):
        raise ValueError("Invalid PDF expectation bounds")
    x, y, right, bottom = value
    if not (0 <= x < right <= SIZE[0] and 0 <= y < bottom <= SIZE[1]):
        raise ValueError("PDF expectation outside page")
    return value


def contains(box, word, tolerance=TOLERANCE):
    return (
        word[0] >= box[0] - tolerance
        and word[1] >= box[1] - tolerance
        and word[2] <= box[2] + tolerance
        and word[3] <= box[3] + tolerance
    )


def verify_pdf_layout(layout_xml: str, expectations: dict, fonts: str) -> dict:
    if expectations.get("schemaVersion") != 1 or expectations.get("pageSizePt") != list(
        SIZE
    ):
        raise ValueError("Invalid PDF expectations")
    embedded = set()
    for line in fonts.splitlines()[2:]:
        fields = line.split()
        if len(fields) < 6:
            continue
        name = fields[0].split("+")[-1]
        if name not in ("DejaVuSans", "DejaVuSans-Bold") or fields[-5] != "yes":
            raise ValueError("PDF font substitution or unembedded font")
        embedded.add(name)
    if embedded != {"DejaVuSans", "DejaVuSans-Bold"}:
        raise ValueError("PDF intended fonts missing")
    root = ET.fromstring(layout_xml)
    pages = [e for e in root.iter() if e.tag.split("}")[-1] == "page"]
    if len(pages) != expectations.get("pageCount") or not pages:
        raise ValueError("PDF page count mismatch")
    page_words = {}
    for number, page in enumerate(pages, 1):
        if any(
            abs(float(page.attrib[k]) - want) > 0.01
            for k, want in zip(("width", "height"), SIZE)
        ):
            raise ValueError("PDF page geometry mismatch")
        words = []
        for element in page.iter():
            if element.tag.split("}")[-1] != "word":
                continue
            bounds = tuple(
                float(element.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax")
            )
            if any(not math.isfinite(v) for v in bounds) or not contains(
                (0, 0, *SIZE), bounds, 0.01
            ):
                raise ValueError("PDF word outside page")
            words.append((element.text or "", bounds))
        page_words[number] = words
    tables = {
        p["page"]: rectangle(p["tableBodyBoundsPt"])
        for p in expectations["pages"]
        if p.get("tableBodyBoundsPt") is not None
    }
    if len(expectations["pages"]) != len(pages) or [
        p["page"] for p in expectations["pages"]
    ] != list(page_words):
        raise ValueError("PDF page assignments mismatch")
    results, used, identities = [], set(), set()
    previous = (0, -1)
    for row in expectations["rows"]:
        number = row["page"]
        identity = (row["legId"], row["rowId"])
        cells, boxes = row["displayCells"], row["cellBoundsPt"]
        if (
            identity in identities
            or number not in tables
            or len(cells) != 4
            or len(boxes) != 4
            or any(not isinstance(v, str) for v in cells)
        ):
            raise ValueError("Invalid or duplicate PDF row assignment")
        identities.add(identity)
        boxes = [rectangle(b) for b in boxes]
        position = (number, boxes[0][1])
        if position <= previous:
            raise ValueError("PDF row assignment order mismatch")
        previous = position
        for index, (cell, box) in enumerate(zip(cells, boxes)):
            if not contains(tables[number], box, 0.01) or (
                index and box[0] < boxes[index - 1][2] - 0.01
            ):
                raise ValueError("PDF row split or ambiguous cell bounds")
            matches = []
            for word_index, (text, bounds) in enumerate(page_words[number]):
                if contains(box, bounds):
                    key = (number, word_index)
                    if key in used:
                        raise ValueError("PDF word allocated to multiple cells")
                    used.add(key)
                    matches.append((text, bounds))
            matches.sort(key=lambda w: (round(w[1][1], 2), w[1][0]))
            if normalized(" ".join(w[0] for w in matches)) != normalized(cell):
                raise ValueError("PDF coordination cell content mismatch")
        results.append(
            {
                "legId": row["legId"],
                "rowId": row["rowId"],
                "page": number,
                "displayCells": cells,
                "cellsMatched": True,
                "inBounds": True,
            }
        )
    inspection = {
        p["page"]: rectangle(p.get("tableInspectionBoundsPt") or p["tableBodyBoundsPt"])
        for p in expectations["pages"]
        if p.get("tableBodyBoundsPt") is not None
    }
    for number, box in inspection.items():
        for index, (_, bounds) in enumerate(page_words[number]):
            if contains(box, bounds) and (number, index) not in used:
                raise ValueError("PDF has unassigned coordination text")
    return {
        "verified": True,
        "pageCount": len(pages),
        "pageSizePt": list(SIZE),
        "rows": results,
        "fonts": sorted(embedded),
    }


def run_pdf_command(args, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("PDF verification deadline")
    child = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    )
    try:
        stdout, _stderr = child.communicate(timeout=remaining)
        if child.returncode:
            raise ValueError("PDF inspection command failed")
        return stdout.decode("utf-8")
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=min(0.25, max(0, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


def verify_customer_pdf(
    pdf_path: Path, expectations: dict, *, timeout_seconds: float
) -> dict:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("PDF verification requires remaining time")
    deadline = time.monotonic() + timeout_seconds
    info = run_pdf_command(["pdfinfo", str(pdf_path)], deadline)
    count = re.search(r"Pages:\s+(\d+)", info)
    if not count or int(count[1]) != expectations["pageCount"]:
        raise ValueError("PDF page count mismatch")
    fonts = run_pdf_command(["pdffonts", str(pdf_path)], deadline)
    layout = run_pdf_command(
        ["pdftotext", "-bbox-layout", str(pdf_path), "-"], deadline
    )
    result = verify_pdf_layout(layout, expectations, fonts)
    if time.monotonic() > deadline:
        raise TimeoutError("PDF verification deadline")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("expectations", type=Path)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    args = parser.parse_args()
    result = verify_customer_pdf(
        args.pdf,
        json.loads(args.expectations.read_text()),
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
