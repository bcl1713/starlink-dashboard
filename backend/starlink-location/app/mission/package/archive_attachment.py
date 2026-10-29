"""Verify immutable sidecars and stream supplementary members into mission ZIPs."""

import copy
import hashlib
import json
import zipfile

from app.mission.exporter.export_cancel import check_cancelled

from .streams import iter_zip_blocks, new_package_stream


def canonical(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def append_archive(
    stream, snapshot, *, planning_fingerprint, cancel, output=None, artifact_store=None
):
    """Copy existing members byte-for-byte; publish exactly one outer manifest."""
    result = output if output is not None else new_package_stream()
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream) as source, zipfile.ZipFile(
            result, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            manifest = json.loads(source.read("manifest.json"))
            files = snapshot["files"]
            if set(files) & set(source.namelist()):
                raise ValueError("Archive component path collision")
            for entry in source.infolist():
                check_cancelled(cancel)
                if entry.filename == "manifest.json":
                    continue
                with source.open(entry) as incoming, target.open(
                    copy.copy(entry), "w"
                ) as outgoing:
                    for block in iter_zip_blocks(incoming):
                        check_cancelled(cancel)
                        outgoing.write(block)
            for name, text in files.items():
                check_cancelled(cancel)
                target.writestr(name, text.encode("utf-8"))
            attachment_checksums = {}
            for attachment in snapshot.get("attachments", []):
                if artifact_store is None:
                    raise RuntimeError("Export artifact store is unavailable")
                with artifact_store.path(attachment).open("rb") as incoming:
                    digest = hashlib.sha256()
                    for block in iter_zip_blocks(incoming):
                        check_cancelled(cancel)
                        digest.update(block)
                    if digest.hexdigest() != attachment["sha256"]:
                        raise RuntimeError("Telemetry snapshot checksum mismatch")
                    incoming.seek(0)
                    with zipfile.ZipFile(incoming) as telemetry:
                        if set(telemetry.namelist()) != set(attachment["members"]):
                            raise RuntimeError("Telemetry snapshot member mismatch")
                        for name, metadata in attachment["members"].items():
                            path = "telemetry/" + name
                            if (
                                path in target.namelist()
                                or name.startswith("/")
                                or ".." in name.split("/")
                            ):
                                raise ValueError("Archive component path collision")
                            digest, size = hashlib.sha256(), 0
                            with telemetry.open(name) as source_member, target.open(
                                path, "w", force_zip64=True
                            ) as target_member:
                                for block in iter_zip_blocks(source_member):
                                    check_cancelled(cancel)
                                    size += len(block)
                                    if size > metadata["size"]:
                                        raise RuntimeError(
                                            "Telemetry snapshot size mismatch"
                                        )
                                    digest.update(block)
                                    target_member.write(block)
                            if (
                                size != metadata["size"]
                                or digest.hexdigest() != metadata["sha256"]
                            ):
                                raise RuntimeError("Telemetry member checksum mismatch")
                            attachment_checksums[path] = digest.hexdigest()
            manifest["archive_components"] = {
                "schema_version": 1,
                "capture_policy": snapshot["capture_policy"],
                "planning_fingerprint": planning_fingerprint,
                "components": snapshot["components"],
                "checksums": {
                    name: hashlib.sha256(text.encode("utf-8")).hexdigest()
                    for name, text in files.items()
                }
                | attachment_checksums,
                "import_policy": "planning_only; archival_components_do_not_restore_active_stores",
            }
            manifest["file_structure"]["archive_files"] = sorted(
                set(files) | set(attachment_checksums)
            )
            manifest["statistics"]["total_files"] = len(target.namelist()) + 1
            target.writestr("manifest.json", canonical(manifest))
        check_cancelled(cancel)
        result.seek(0)
        return result
    except BaseException:
        result.close()
        raise
