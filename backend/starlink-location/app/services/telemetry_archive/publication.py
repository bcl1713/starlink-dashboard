"""Publish durable CSV ZIP projections of immutable sealed snapshots."""

import hashlib
import json
import os
from uuid import uuid4


def publish_sealed(archive):
    from app.services.telemetry_archive.package import build_telemetry_package

    directory = archive.ledger.path.parent / "sealed"
    directory.mkdir(parents=True, exist_ok=True)
    for summary in archive.all_captures():
        if summary["state"] != "sealed":
            continue
        identity = json.dumps(
            [summary["mission_id"], summary["leg_id"], summary["revision"]]
        )
        target = directory / (hashlib.sha256(identity.encode()).hexdigest() + ".zip")
        if target.exists():
            continue
        capture = archive.capture(
            summary["mission_id"], summary["leg_id"], summary["revision"]
        )
        temporary = directory / (target.name + "." + str(uuid4()) + ".tmp")
        try:
            with temporary.open("wb") as stream:
                stream.write(
                    build_telemetry_package(
                        summary["mission_id"], [capture], allow_partial=True
                    )
                )
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
