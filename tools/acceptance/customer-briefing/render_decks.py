#!/usr/bin/env python3
"""Offline acceptance-only LibreOffice render, raster pages and grayscale sheets."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def render(root):
    from PIL import Image, ImageDraw

    (root / "libreoffice-version.txt").write_text(
        subprocess.check_output(["libreoffice", "--version"], text=True)
    )
    (root / "render-packages.txt").write_bytes(
        Path("/render-packages.txt").read_bytes()
    )
    reports = {}
    for deck in sorted(root.rglob("*.pptx")):
        folder = deck.parent / f"{deck.stem}-render"
        folder.mkdir(exist_ok=False)
        with tempfile.TemporaryDirectory(prefix="customer-briefing-lo-") as profile:
            subprocess.run(
                [
                    "timeout",
                    "--kill-after=10s",
                    "3m",
                    "libreoffice",
                    f"-env:UserInstallation={Path(profile).as_uri()}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(folder),
                    str(deck),
                ],
                check=True,
            )
        pdf = folder / f"{deck.stem}.pdf"
        if not pdf.is_file():
            raise ValueError(f"LibreOffice did not produce {pdf}")
        subprocess.run(
            [
                "timeout",
                "--kill-after=10s",
                "3m",
                "pdftoppm",
                "-png",
                "-scale-to",
                "1800",
                str(pdf),
                str(folder / "page"),
            ],
            check=True,
        )
        subprocess.run(
            [
                "timeout",
                "--kill-after=10s",
                "1m",
                "pdftotext",
                "-bbox-layout",
                str(pdf),
                str(folder / "text.html"),
            ],
            check=True,
        )
        pages = sorted(folder.glob("page-*.png"))
        if not pages:
            raise ValueError("render produced no pages")
        # Preserve grayscale for every page; only trial primary pages enter sheets.
        inspection = deck.parent / "inspection.json"
        info = (
            json.loads(inspection.read_text()).get(deck.stem, {})
            if inspection.exists()
            else {}
        )
        if info and len(pages) != len(info["slides"]):
            raise ValueError("PDF/slide page count mismatch")
        primary = [
            page
            for number, page in enumerate(pages, 1)
            if not info or info["slides"][number - 1]["primary"]
        ]
        for page in pages:
            with Image.open(page) as image:
                image.convert("L").save(page.with_name(page.stem + "-gray.png"))
        for offset in range(0, len(primary), 12):
            batch = primary[offset : offset + 12]
            for gray in (False, True):
                canvas = Image.new("RGB", (1200, 1032), "#eeeeee")
                draw = ImageDraw.Draw(canvas)
                for n, page in enumerate(batch):
                    x, y = (n % 3) * 400, (n // 3) * 258
                    selected = page.with_name(page.stem + "-gray.png") if gray else page
                    with Image.open(selected) as image:
                        image.thumbnail((398, 224))
                        canvas.paste(image, (x, y + 24))
                    draw.text(
                        (x + 8, y + 5),
                        f"{deck.parent.name} {deck.stem} {page.stem}",
                        fill="black",
                    )
                canvas.save(
                    folder / f'contact-{offset//12+1}{"-gray" if gray else ""}.png'
                )
        reports[str(deck.relative_to(root))] = {
            "pages": len(pages),
            "primary_pages": len(primary),
            "pdf": str(pdf.relative_to(root)),
            "sheets": [
                str(p.relative_to(root)) for p in sorted(folder.glob("contact-*.png"))
            ],
        }
        print(f"{deck.relative_to(root)}: rendered {len(pages)} pages", flush=True)
    (root / "renders.json").write_text(json.dumps(reports, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    render(parser.parse_args().root.resolve())
