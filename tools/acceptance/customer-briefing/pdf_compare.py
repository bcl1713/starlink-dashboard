"""Compare every PDF page at screen and print resolution without altering inputs."""

import argparse
import json
import os
import signal
import subprocess
import threading
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from pypdf import PdfReader


def _render(pdf, prefix, dpi, journal):
    command = ["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(prefix)]
    ownership = {"command": command, "pid": None, "pgid": None, "reaped": False}
    journal.write_text(json.dumps(ownership, indent=2))
    process = subprocess.Popen(
        command,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    ownership.update(pid=process.pid, pgid=process.pid)
    journal.write_text(json.dumps(ownership, indent=2))
    handlers = {}

    def stop(signum, frame):
        raise InterruptedError("PDF comparison cancelled")

    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGTERM, signal.SIGINT):
            handlers[signum] = signal.signal(signum, stop)
    try:
        _, stderr = process.communicate(timeout=120)
        if process.returncode:
            raise RuntimeError(
                "Poppler comparison failed: " + stderr.decode(errors="replace")[-1000:]
            )
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=10)
        ownership.update(returncode=process.returncode, reaped=True)
        journal.write_text(json.dumps(ownership, indent=2))
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


def compare_pdfs(baseline, candidate, output, *, dpis=(72, 300)):
    baseline, candidate, output = Path(baseline), Path(candidate), Path(output)
    readers = [PdfReader(baseline), PdfReader(candidate)]
    count = len(readers[0].pages)
    if len(readers[1].pages) != count:
        raise ValueError("PDF page count changed")
    if [list(p.mediabox) for p in readers[0].pages] != [
        list(p.mediabox) for p in readers[1].pages
    ]:
        raise ValueError("PDF page geometry changed")
    if [p.extract_text() for p in readers[0].pages] != [
        p.extract_text() for p in readers[1].pages
    ]:
        raise ValueError("PDF searchable text changed")
    output.mkdir(parents=True, exist_ok=False)
    report = {"pageCount": count, "geometryEqual": True, "textEqual": True, "pages": []}
    for dpi in dpis:
        if not isinstance(dpi, int) or dpi <= 0:
            raise ValueError("Comparison DPI must be positive")
        root = output / str(dpi)
        root.mkdir()
        for name, pdf in (("baseline", baseline), ("candidate", candidate)):
            _render(pdf, root / name, dpi, root / (name + "-ownership.json"))
        before, after = sorted(root.glob("baseline-*.png")), sorted(
            root.glob("candidate-*.png")
        )
        if len(before) != count or len(after) != count:
            raise ValueError("Poppler omitted PDF pages")
        for number, (a, b) in enumerate(zip(before, after), 1):
            with Image.open(a) as src_a, Image.open(b) as src_b:
                with src_a.convert("RGB") as left, src_b.convert("RGB") as right:
                    if left.size != right.size:
                        raise ValueError("Rendered PDF page geometry changed")
                    with ImageChops.difference(left, right) as diff:
                        # RGB differences can be smaller than gray rounding.
                        with diff.point(lambda v: 255 if v else 0) as channels:
                            with channels.convert("L") as nonzero:
                                changed = (
                                    left.width * left.height - nonzero.histogram()[0]
                                )
                        report["pages"].append(
                            {
                                "page": number,
                                "dpi": dpi,
                                "changedPixels": changed,
                                "meanChannelError": ImageStat.Stat(diff).mean,
                                "size": list(left.size),
                            }
                        )
                        diff.save(root / f"difference-{number}.png")
    (output / "comparison.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dpi", action="append", type=int)
    args = parser.parse_args()
    print(
        json.dumps(
            compare_pdfs(
                args.baseline, args.candidate, args.output, dpis=args.dpi or (72, 300)
            )
        )
    )
