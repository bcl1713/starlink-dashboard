"""Write-ahead compensation journal, recoverable before any runtime readers.

Callers hold the repository activation lock before the parent lock. The durable
commit marker selects the next state; an interrupted uncommitted record restores
its previous files and only the explicitly owned POI scope.
"""

import base64
import json
import os
from pathlib import Path
from uuid import uuid4

from filelock import FileLock


def atomic_write(path: Path, data: bytes | None):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):
        fd = os.open(created.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    if data is None:
        path.unlink(missing_ok=True)
    else:
        temporary = path.with_name(path.name + ".planning-tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def json_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def scope_matches(poi, scope):
    return (
        poi.get("mission_id") == scope["mission_id"]
        and poi.get("route_id") in scope.get("route_ids", [scope.get("route_id")])
        and poi.get("generated_source") == "mission-timeline"
    )


def read_scope(path, scope):
    with FileLock(str(path) + ".lock"):
        data = json.loads(path.read_bytes())
        return {
            key: poi
            for key, poi in data.get("pois", {}).items()
            if scope_matches(poi, scope)
        }


def replace_scope(path, scope, records):
    with FileLock(str(path) + ".lock"):
        data = json.loads(path.read_bytes())
        retained = {
            key: poi
            for key, poi in data.get("pois", {}).items()
            if not scope_matches(poi, scope)
        }
        if set(retained) & set(records):
            raise ValueError("Owned POI IDs collide with unrelated records")
        if any(not scope_matches(poi, scope) for poi in records.values()):
            raise ValueError("POI outside transaction ownership scope")
        data["pois"] = {**retained, **records}
        atomic_write(path, json_bytes(data))


class Journal:
    def __init__(self, root: Path, routes_dir: Path, pois_file: Path):
        self.root = root.resolve()
        self.routes_dir = routes_dir.resolve()
        self.pois_file = pois_file.resolve()
        self.directory = self.root / ".planning" / "journals"

    def _check_path(self, path):
        path = Path(path)
        resolved = path.resolve()
        if resolved != path or not (
            resolved.is_relative_to(self.root)
            or (
                resolved.parent == self.routes_dir
                and resolved.suffix in {".kml", ".json"}
            )
        ):
            raise ValueError("Journal path is outside owned storage")
        return resolved

    def _restore(self, record):
        if record.get("version") != 1 or record.get("state") not in {
            "prepared",
            "committed",
        }:
            raise ValueError("Unsupported or malformed planning journal")
        # Validate the complete record before performing any recovery write.
        entries = [
            (
                self._check_path(item["path"]),
                (
                    base64.b64decode(item["before"], validate=True)
                    if item["before"] is not None
                    else None
                ),
            )
            for item in record["files"]
        ]
        poi = record.get("poi")
        if poi and (
            Path(poi["path"]).resolve() != self.pois_file
            or not isinstance(poi["before"], dict)
        ):
            raise ValueError("Invalid planning journal POI ownership")
        if record["state"] == "committed":
            return
        for path, before in reversed(entries):
            atomic_write(path, before)
        if poi:
            replace_scope(self.pois_file, poi["scope"], poi["before"])

    def recover(self):
        if not self.directory.exists():
            return
        for path in sorted(self.directory.glob("*.json")):
            self._restore(json.loads(path.read_bytes()))
            atomic_write(path, None)

    def commit(
        self,
        files: dict[Path, bytes | None],
        *,
        poi_scope=None,
        pois=None,
        after_write=None,
    ):
        record = {"version": 1, "state": "prepared", "files": []}
        for path in files:
            path = self._check_path(str(path.resolve()))
            record["files"].append(
                {
                    "path": str(path),
                    "before": (
                        base64.b64encode(path.read_bytes()).decode()
                        if path.exists()
                        else None
                    ),
                }
            )
        if poi_scope is not None:
            record["poi"] = {
                "path": str(self.pois_file),
                "scope": poi_scope,
                "before": read_scope(self.pois_file, poi_scope),
            }
        journal_path = self.directory / f"{uuid4()}.json"
        atomic_write(journal_path, json_bytes(record))
        try:
            for index, (path, data) in enumerate(files.items()):
                atomic_write(path, data)
                if after_write:
                    after_write(index, path)
            if poi_scope is not None:
                replace_scope(self.pois_file, poi_scope, pois or {})
                if after_write:
                    after_write(len(files), self.pois_file)
            record["state"] = "committed"
            atomic_write(journal_path, json_bytes(record))
        except Exception:
            # Keep the prepared journal if compensation itself fails; fail closed.
            # A marker rename may have succeeded before its fsync raised. In
            # that case every new value is already present; never roll back
            # while a committed on-disk marker could select partial new state.
            persisted = json.loads(journal_path.read_bytes())
            self._restore(persisted)
            atomic_write(journal_path, None)
            raise
        atomic_write(journal_path, None)
