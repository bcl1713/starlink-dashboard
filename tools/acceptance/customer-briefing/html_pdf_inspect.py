"""Inspect the delivered PDF, independently of the browser preview."""

import re
import subprocess
import xml.etree.ElementTree as ET
from hashlib import sha256
from pathlib import Path

from PIL import Image


def command(args):
    return subprocess.run(
        args, check=True, capture_output=True, text=True, timeout=30
    ).stdout


def inspect_pdf(
    pdf_path: Path, html_png_path: Path, expectations: dict | None = None
) -> dict:
    info = command(["pdfinfo", str(pdf_path)])
    count = int(re.search(r"Pages:\s+(\d+)", info)[1])
    size = [
        float(v)
        for v in re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", info).groups()
    ]
    if count != 1 or any(abs(a - b) > 0.01 for a, b in zip(size, (960, 540))):
        raise ValueError("PDF page count/geometry mismatch")
    text = command(["pdftotext", "-layout", str(pdf_path), "-"])
    for required in (
        "LEG 1 OF 1",
        "KADW",
        "PAED",
        "25 Oct 2026",
        "10:00",
        "18:00",
        "8h 00m",
        "Starshield",
        "SOF",
        "COORDINATION WINDOWS",
    ):
        if required not in text:
            raise ValueError("Delivered PDF customer text missing: " + required)
    fonts = command(["pdffonts", str(pdf_path)])
    if "DejaVuSans" not in fonts or "DejaVuSans-Bold" not in fonts:
        raise ValueError("PDF font substitution")
    xml = command(["pdftotext", "-bbox", str(pdf_path), "-"])
    words = []
    for element in ET.fromstring(xml).iter():
        if element.tag.endswith("word"):
            bounds = {
                k: float(element.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax")
            }
            if (
                bounds["xMin"] < 0
                or bounds["yMin"] < 0
                or bounds["xMax"] > size[0] + 0.01
                or bounds["yMax"] > size[1] + 0.01
            ):
                raise ValueError("PDF word outside page")
            words.append({"text": element.text, **bounds})
    images = {}
    for mode in ("color", "grayscale"):
        prefix = pdf_path.parent / ("pdf-" + mode)
        args = ["pdftoppm", "-r", "240", "-png", "-singlefile"]
        if mode == "grayscale":
            args.append("-gray")
        command([*args, str(pdf_path), str(prefix)])
        image_path = prefix.with_suffix(".png")
        with Image.open(image_path) as image:
            if image.size != (3200, 1800):
                raise ValueError("PDF raster size mismatch")
            images[mode] = {
                "file": image_path.name,
                "pixelHash": sha256(image.convert("RGBA").tobytes()).hexdigest(),
            }
            if mode == "color":
                for name, box in {
                    "header": (0, 0, 3200, 370),
                    "timeline": (0, 370, 3200, 1000),
                    "table": (50, 1000, 2470, 1730),
                    "patch": (2910, 20, 3180, 355),
                    "map": (2470, 1000, 3160, 1730),
                }.items():
                    image.crop(box).save(pdf_path.parent / f"pdf-crop-{name}.png")
    with Image.open(html_png_path) as preview:
        if preview.size != (3200, 1800):
            raise ValueError("HTML preview size mismatch")
        preview_hash = sha256(preview.convert("RGBA").tobytes()).hexdigest()
    row_validation = {}
    if expectations is not None:
        from app.mission.exporter.customer_pdf import verify_customer_pdf

        row_validation = verify_customer_pdf(pdf_path, expectations, timeout_seconds=30)
    return {
        "verified": True,
        "pageCount": count,
        "pageSizePt": size,
        "pdfRasterSize": [3200, 1800],
        "previewSize": [3200, 1800],
        "text": text,
        "words": words,
        "fonts": fonts,
        "images": images,
        "previewPixelHash": preview_hash,
        "rows": row_validation.get("rows"),
    }


def normalized_pdf_hash(path):
    raw = Path(path).read_bytes()
    raw = re.sub(rb"/(CreationDate|ModDate)\s*\(D:[^)]*\)", rb"/\1 (D:normalized)", raw)
    raw = re.sub(rb"/ID\s*\[\s*<[^>]*>\s*<[^>]*>\s*\]", b"/ID [normalized]", raw)
    return sha256(raw).hexdigest()
