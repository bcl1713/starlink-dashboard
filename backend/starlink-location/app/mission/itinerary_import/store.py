"""Durable private uploads, operation generations and bounded admission."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from filelock import FileLock

from app.mission.planning.journal import atomic_write, json_bytes

from .models import ImportOperation

TERMINAL = {"committed", "cancelled", "failed"}


class ImportStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.root / ".operations.lock")

    def directory(self, id):
        if not re.fullmatch(r"[a-f0-9]{32}", id):
            raise ValueError("Invalid import operation ID")
        return self.root / id

    def read(self, id):
        return ImportOperation.model_validate_json(
            (self.directory(id) / "operation.json").read_bytes()
        )

    def payload(self, id):
        return json.loads((self.directory(id) / "input.json").read_bytes())

    def create(self, pdf, kmls, key, mission_id=None):
        if (
            not key
            or len(key) > 200
            or not pdf
            or len(pdf) > 10 * 1024 * 1024
            or not (0 if mission_id else 1) <= len(kmls) <= 16
            or sum(len(b) for _, b in kmls) > 40 * 1024 * 1024
        ):
            raise ValueError(
                "Upload requires a PDF up to 10 MiB and 1–16 KMLs up to 40 MiB total"
            )
        if mission_id is not None and not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", mission_id
        ):
            raise ValueError("Invalid mission ID")
        digest = hashlib.sha256(
            json_bytes(
                {
                    "pdf": hashlib.sha256(pdf).hexdigest(),
                    "kmls": [
                        (name, hashlib.sha256(data).hexdigest()) for name, data in kmls
                    ],
                    "mission": mission_id,
                }
            )
        ).hexdigest()
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        with self.lock:
            index_path = self.root / "keys.json"
            keys = json.loads(index_path.read_bytes()) if index_path.exists() else {}
            if key_hash in keys:
                previous = keys[key_hash]
                if previous["digest"] != digest:
                    raise ValueError("Idempotency key used for different uploads")
                return self.read(previous["id"])
            if (
                len(
                    [
                        p
                        for p in self.root.glob("*/operation.json")
                        if ImportOperation.model_validate_json(p.read_bytes()).state
                        not in TERMINAL
                    ]
                )
                >= 9
            ):
                raise OverflowError("Import queue full; retry later")
            id = uuid4().hex
            op = ImportOperation(
                id=id,
                mission_id=mission_id or str(uuid4()),
                revision=mission_id is not None,
                deadline=datetime.now(timezone.utc) + timedelta(minutes=20),
            )
            directory = self.directory(id)
            directory.mkdir()
            atomic_write(directory / "source.pdf", pdf)
            files = []
            for i, (name, data) in enumerate(kmls):
                rid = uuid4().hex
                atomic_write(directory / f"{rid}.kml", data)
                files.append({"id": rid, "name": Path(name).name})
            atomic_write(
                directory / "input.json",
                json_bytes({"files": files, "digest": digest, "choices": {}}),
            )
            atomic_write(
                directory / "operation.json", json_bytes(op.model_dump(mode="json"))
            )
            keys[key_hash] = {"id": id, "digest": digest}
            atomic_write(index_path, json_bytes(keys))
            return op

    def update(self, id, generation, **changes):
        with self.lock:
            current = self.read(id)
            if current.generation != generation:
                raise ValueError("Import operation generation is stale")
            if current.state in TERMINAL:
                raise ValueError("Import operation is already finished")
            updated = ImportOperation.model_validate(
                {**current.model_dump(), **changes, "generation": generation + 1}
            )
            atomic_write(
                self.directory(id) / "operation.json",
                json_bytes(updated.model_dump(mode="json")),
            )
            return updated

    def pending(self):
        with self.lock:
            result = []
            for path in self.root.glob("*/operation.json"):
                op = ImportOperation.model_validate_json(path.read_bytes())
                if op.state in TERMINAL:
                    continue
                if op.deadline <= datetime.now(timezone.utc):
                    self.update(
                        op.id,
                        op.generation,
                        state="failed",
                        error="Import deadline exceeded",
                    )
                elif op.state in {"running", "queued", "ready"}:
                    result.append(op)
            return sorted(result, key=lambda operation: operation.deadline)
