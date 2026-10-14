"""Prepare a deterministic print PNG; never modify the brand master."""

import argparse
from pathlib import Path

from PIL import Image


def resize_logo(source: Path, output: Path, size: int) -> None:
    if size <= 0 or source.resolve() == output.resolve():
        raise ValueError("Use a positive size and a separate derivative path")
    with Image.open(source) as image:
        profile = image.info.get("icc_profile")
        with image.convert("RGB") as rgb:
            with rgb.resize((size, size), Image.Resampling.LANCZOS) as resized:
                resized.save(
                    output, format="PNG", compress_level=9, optimize=False,
                    icc_profile=profile,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, required=True)
    args = parser.parse_args()
    resize_logo(args.source, args.output, args.size)
