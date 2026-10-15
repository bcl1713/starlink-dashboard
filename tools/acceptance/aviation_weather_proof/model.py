"""Immutable records and explicitly loaded, confined offline source bindings."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from .exchange import validate_url

MAX_OBJECT_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class CapturedObject:
    url: str
    byte_range: tuple[int, int] | None
    relative_path: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class CaptureManifest:
    source: str
    captured_at_ms: int
    objects: tuple[CapturedObject, ...]
    attribution: tuple[str, ...]


@dataclass(frozen=True)
class ProductArtifact:
    descriptor_path: Path
    payload_paths: tuple[Path, ...]
    capture_manifest_path: Path


# Each process must load its manifest. Constructor fields remain serializable.
_BINDINGS: dict[CaptureManifest, tuple[Path, str]] = {}


def confined(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("object path must be confined and relative")
    candidate = root / path
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("object path escapes source root")
    return candidate


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def validate_object(root: Path, obj: CapturedObject) -> Path:
    validate_url(obj.url)
    if obj.byte_range is not None:
        if (
            len(obj.byte_range) != 2
            or any(type(n) is not int for n in obj.byte_range)
            or not 0 <= obj.byte_range[0] <= obj.byte_range[1]
            or obj.byte_range[1] - obj.byte_range[0] + 1 != obj.byte_size
        ):
            raise ValueError("manifest byte range does not match object size")
    if not isinstance(obj.byte_size, int) or not 0 < obj.byte_size <= MAX_OBJECT_BYTES:
        raise ValueError("invalid object size; cap 32 MiB")
    path = confined(root, obj.relative_path)
    if (
        not path.is_file()
        or path.stat().st_size != obj.byte_size
        or file_hash(path) != obj.sha256
    ):
        raise ValueError("source hash/size changed or object departed")
    return path


def write_manifest(manifest: CaptureManifest, path: Path) -> None:
    path.write_text(json.dumps(asdict(manifest), indent=2) + "\n")


def load_capture(manifest_path: Path) -> CaptureManifest:
    try:
        path = Path(manifest_path).resolve()
    except TypeError as error:
        raise ValueError("invalid capture manifest path") from error
    if not path.is_file():
        raise ValueError("capture manifest departed or is unavailable")
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("manifest too large")
    data = json.loads(path.read_text())
    # Validate JSON field types before path parsing or hashing frozen records.
    # Converting arbitrary containers to tuples can otherwise hide bad inputs
    # or leave unhashable nested objects inside the manifest registry key.
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("source"), str)
        or type(data.get("captured_at_ms")) is not int
        or not isinstance(data.get("objects"), list)
        or not isinstance(data.get("attribution"), list)
        or any(not isinstance(item, str) for item in data["attribution"])
    ):
        raise ValueError("invalid manifest field types")
    for item in data["objects"]:
        if (
            not isinstance(item, dict)
            or any(
                not isinstance(item.get(field), str)
                for field in ("url", "relative_path", "sha256")
            )
            or type(item.get("byte_size")) is not int
            or (
                item.get("byte_range") is not None
                and (
                    not isinstance(item["byte_range"], list)
                    or any(type(value) is not int for value in item["byte_range"])
                )
            )
        ):
            raise ValueError("invalid captured object field types")
    try:
        objects = tuple(
            CapturedObject(
                **{
                    **o,
                    "byte_range": tuple(o["byte_range"])
                    if o["byte_range"] is not None
                    else None,
                }
            )
            for o in data["objects"]
        )
        manifest = CaptureManifest(
            data["source"], data["captured_at_ms"], objects, tuple(data["attribution"])
        )
    except (TypeError, KeyError) as error:
        raise ValueError("invalid manifest") from error
    if (
        manifest.source not in ("gfs", "isigmet", "goes19-c13")
        or not objects
        or len(objects) > 4
    ):
        raise ValueError("invalid manifest source/objects")
    if (
        not isinstance(manifest.captured_at_ms, int)
        or manifest.captured_at_ms <= 0
        or not manifest.attribution
    ):
        raise ValueError("invalid manifest provenance")
    for obj in objects:
        validate_object(path.parent, obj)
    _BINDINGS[manifest] = (path, file_hash(path))
    return manifest


def capture_manifest_path(manifest: CaptureManifest) -> Path:
    try:
        path, digest = _BINDINGS[manifest]
    except KeyError as error:
        raise ValueError("explicit load_capture required in this worker") from error
    if not path.is_file() or file_hash(path) != digest:
        raise ValueError("manifest hash changed")
    return path


def object_path(manifest: CaptureManifest, obj: CapturedObject) -> Path:
    root = capture_manifest_path(manifest).parent
    if obj not in manifest.objects:
        raise ValueError("object does not belong to manifest")
    return validate_object(root, obj)
