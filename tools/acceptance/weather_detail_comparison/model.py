"""Portable, hashed identities for offline weather-source evidence."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class TileKey:
    z: int
    x: int
    y: int

    def __post_init__(self):
        if any(type(v) is not int for v in (self.z, self.x, self.y)):
            raise ValueError("integer XYZ required")
        if (
            not 2 <= self.z <= 7
            or not 0 <= self.x < 2**self.z
            or not 0 <= self.y < 2**self.z
        ):
            raise ValueError("XYZ outside supported range")


@dataclass(frozen=True)
class Snapshot:
    source: str
    product: str
    observed_utc: int
    captured_utc: int
    units: str
    crs: str
    source_url: str
    license: str
    attribution: str
    local_path: Path
    sha256: str

    @property
    def identity(self):
        return f"{self.source}-{self.product}-{self.observed_utc}-{self.sha256[:12]}"


@dataclass(frozen=True)
class TilePair:
    snapshot_identity: str
    radar_path: Path
    absence_path: Path
    radar_sha256: str
    absence_sha256: str


@dataclass(frozen=True)
class CaptureSet:
    root: Path
    snapshots: tuple[Snapshot, ...]
    tiles: dict[str, dict[TileKey, TilePair]]
    metadata: dict


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(root, path):
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError as error:
        raise ValueError("capture path escapes root") from error


def local(root, value):
    path = root / value
    relative(root, path)
    return path


def validate(captures):
    identities = set()
    for snapshot in captures.snapshots:
        if snapshot.source not in {"rainviewer", "mrms", "opera"}:
            raise ValueError("unsupported snapshot source")
        if sum(s.source == snapshot.source for s in captures.snapshots) > 2:
            raise ValueError("snapshot limit exceeded")
        if (
            type(snapshot.observed_utc) is not int
            or not 0 < snapshot.observed_utc <= snapshot.captured_utc
        ):
            raise ValueError("invalid observation timestamp")
        if not all(
            (snapshot.units, snapshot.crs, snapshot.license, snapshot.attribution)
        ):
            raise ValueError("incomplete provenance")
        relative(captures.root, snapshot.local_path)
        if digest(snapshot.local_path) != snapshot.sha256:
            raise ValueError("snapshot hash mismatch")
        if snapshot.identity in identities:
            raise ValueError("duplicate snapshot")
        identities.add(snapshot.identity)
    for identity, tiles in captures.tiles.items():
        if identity not in identities:
            raise ValueError("unknown tile snapshot")
        for pair in tiles.values():
            if pair.snapshot_identity != identity:
                raise ValueError("mixed frame tile pair")
            for path, sha in (
                (pair.radar_path, pair.radar_sha256),
                (pair.absence_path, pair.absence_sha256),
            ):
                relative(captures.root, path)
                if digest(path) != sha:
                    raise ValueError("tile hash mismatch")
                from PIL import Image

                with Image.open(path) as image:
                    if image.size != (512, 512):
                        raise ValueError("tile dimensions")


def write_capture(captures: CaptureSet) -> Path:
    validate(captures)
    data = {"version": 1, "snapshots": [], "tiles": {}, "metadata": captures.metadata}
    for snapshot in captures.snapshots:
        entry = asdict(snapshot)
        entry["local_path"] = relative(captures.root, snapshot.local_path)
        data["snapshots"].append(entry)
    for identity, tiles in captures.tiles.items():
        entries = []
        for key, pair in tiles.items():
            entry = asdict(pair)
            for field in ("radar_path", "absence_path"):
                entry[field] = relative(captures.root, getattr(pair, field))
            entries.append({"key": asdict(key), "pair": entry})
        data["tiles"][identity] = entries
    path = captures.root / "capture.json"
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)
    return path


def load_capture(path: Path) -> CaptureSet:
    root = path.resolve().parent
    data = json.loads(path.read_text())
    if data["version"] != 1:
        raise ValueError("capture version")
    snapshots = []
    for entry in data["snapshots"]:
        entry["local_path"] = local(root, entry["local_path"])
        snapshots.append(Snapshot(**entry))
    tiles = {}
    for identity, entries in data["tiles"].items():
        tiles[identity] = {}
        for entry in entries:
            pair = entry["pair"]
            for field in ("radar_path", "absence_path"):
                pair[field] = local(root, pair[field])
            tiles[identity][TileKey(**entry["key"])] = TilePair(**pair)
    result = CaptureSet(root, tuple(snapshots), tiles, data["metadata"])
    validate(result)
    return result
