"""Checkpointed regional tiles matched to the saved raw observation times."""

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

from .capture import MIB, Downloader, RateLimited
from .generate import region_keys
from .model import TileKey, TilePair, digest, load_capture, write_capture


def plan_comparisons(captures):
    rv = next(s for s in captures.snapshots if s.source == "rainviewer")
    frames = json.loads(rv.local_path.read_text())["radar"]["past"]
    snapshots = [s for s in captures.snapshots if s.source != "rainviewer"]
    comparisons = []
    for raw in snapshots:
        region = captures.metadata["regions"].get(raw.source)
        if region is None:
            continue
        frame = min(frames, key=lambda f: abs(f["time"] - raw.observed_utc))
        delta = frame["time"] - raw.observed_utc
        if abs(delta) > 300:
            raise ValueError("observations differ by more than five minutes")
        matched = replace(rv, observed_utc=frame["time"])
        if matched not in snapshots:
            snapshots.append(matched)
        comparisons.append(
            {
                "source": raw.source,
                "raw_identity": raw.identity,
                "rainviewer_identity": matched.identity,
                "radar_path": frame["path"],
                "delta_seconds": delta,
                "region": region,
                "coverage_captured_utc": rv.captured_utc,
            }
        )
    metadata = dict(captures.metadata)
    metadata["comparisons"] = comparisons
    return replace(captures, snapshots=tuple(snapshots), metadata=metadata)


def fetch_tiles(captures):
    downloader = Downloader(captures.root)
    tiles = dict(captures.tiles)
    try:
        for comparison in captures.metadata["comparisons"]:
            identity = comparison["rainviewer_identity"]
            stamp = next(
                s.observed_utc for s in captures.snapshots if s.identity == identity
            )
            existing = dict(tiles.get(identity, {}))
            tiles[identity] = existing
            keys = tuple(TileKey(2, x, y) for x in range(4) for y in range(4))
            region = comparison["region"]
            for level in (5, 6, 7):
                keys += region_keys(region["latitude"], region["longitude"], level)
            for key in keys:
                if key in existing:
                    continue
                suffix = f"512/{key.z}/{key.x}/{key.y}"
                filename = f"rainviewer-{stamp}/{key.z}/{key.x}/{key.y}"
                radar = downloader.get(
                    "https://tilecache.rainviewer.com"
                    + comparison["radar_path"]
                    + "/"
                    + suffix
                    + "/2/1_1.png",
                    filename + "-radar.png",
                    limit=2 * MIB,
                )
                absence = downloader.get(
                    "https://tilecache.rainviewer.com/v2/coverage/0/" + suffix + ".png",
                    filename + "-absence.png",
                    limit=2 * MIB,
                )
                existing[key] = TilePair(
                    identity, radar, absence, digest(radar), digest(absence)
                )
    finally:
        write_capture(replace(captures, tiles=tiles))


def main(root, finish):
    captures = plan_comparisons(load_capture(root / "capture.json"))
    write_capture(captures)
    deadline = time.monotonic() + 12 * 60
    while True:
        try:
            fetch_tiles(load_capture(root / "capture.json"))
            print("Matched base and detail capture complete", flush=True)
            return
        except RateLimited as error:
            if not finish or time.monotonic() + 61 > deadline:
                raise
            print(str(error) + "; checkpoint saved, waiting for allowance", flush=True)
            time.sleep(61)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--finish", action="store_true")
    args = parser.parse_args()
    main(args.root, args.finish)
