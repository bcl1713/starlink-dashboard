"""Owned synthetic long-duration archive and real HTTP upload boundary probes."""

import gc
import hashlib
import io
import json
import resource
import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.mission.package.operations_archive import append_archive
from app.mission.package.preparation_store import ExportPreparation, PreparationStore
from app.mission.slide_cache.store import SlideStore

ROOT = Path("/app/data/operator/archive-acceptance")
MIB = 1024 * 1024


def hwm():
    servers = []
    for process in Path("/proc").glob("[0-9]*"):
        try:
            arguments = (process / "cmdline").read_bytes().split(b"\x00")
            if b"backend_fixture:app" not in arguments or not any(
                Path(arg.decode()).name == "uvicorn" for arg in arguments[:3] if arg
            ):
                continue
            servers.append(
                next(
                    int(line.split()[1]) * 1024
                    for line in (process / "status").read_text().splitlines()
                    if line.startswith("VmHWM:")
                )
            )
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert len(servers) == 1, servers
    return servers[0]


def journal(client):
    response = client.get(
        "/api/v2/operator/records", params={"mission_id": "synthetic-mission-a"}
    )
    response.raise_for_status()
    page = response.json()
    return page["H"], page["items"]


def upload(client, path):
    with path.open("rb") as stream:
        return client.post(
            "/api/v2/missions/import",
            files={"file": (path.name, stream, "application/zip")},
        )


def run():
    started = time.monotonic()
    result = {
        "synthetic": True,
        "coverage": "Large fixture exercises frozen-supplement persistence, ZIP assembly and HTTP import; not source capture capacity. Full capture is covered by singlePackageRoundTrip.",
        "source": "36-hour, 13-channel, 1 Hz CSV size fixture; not aircraft observations",
    }
    with tempfile.TemporaryDirectory(prefix="archive-limits-", dir=ROOT) as temporary:
        directory = Path(temporary)
        original = ROOT / "synthetic-complete-mission.zip"
        with zipfile.ZipFile(original) as archive:
            snapshot = {
                "schema_version": 1,
                "capture_policy": "sequential_component_snapshots",
                "components": json.loads(archive.read("manifest.json"))[
                    "archive_components"
                ]["components"],
                "files": {
                    name: archive.read(name).decode()
                    for name in archive.namelist()
                    if name.startswith(("operations/", "telemetry/"))
                },
            }
            core = io.BytesIO()
            with zipfile.ZipFile(core, "w", zipfile.ZIP_DEFLATED) as output:
                for name in archive.namelist():
                    if name.startswith(("operations/", "telemetry/")):
                        continue
                    body = archive.read(name)
                    if name == "mission.json":
                        mission = json.loads(body)
                        mission["id"] = "synthetic-large-archive-transfer"
                        mission["name"] = "Synthetic Long Archive Transfer"
                        body = json.dumps(mission).encode()
                    if name == "manifest.json":
                        manifest = json.loads(body)
                        manifest.pop("archive_components", None)
                        body = json.dumps(manifest).encode()
                    output.writestr(name, body)
        # Ordinary numeric observation rows with UTC timestamps, metric names,
        # labels and freshness columns. Both legs are retained; no opaque padding
        # is used for the long-duration transfer test.
        count, total = 0, 0
        telemetry_manifest = json.loads(snapshot["files"]["telemetry/manifest.json"])
        for leg in (1, 2):
            csv = io.StringIO()
            csv.write(
                "timestamp_utc,metric,labels_json,value,availability,source_observed_at_utc\n"
            )
            start = datetime(2026, 10, 15, tzinfo=timezone.utc) + timedelta(
                hours=(leg - 1) * 18
            )
            for second in range(18 * 3600):
                stamp = (start + timedelta(seconds=second)).isoformat()
                for metric in range(13):
                    value = ((second * 7919 + metric * 17) % 100000) / 1000
                    csv.write(
                        f"{stamp},synthetic_channel_{metric},{{}},{value},observed,{stamp}\n"
                    )
                    count += 1
            text = csv.getvalue()
            total += len(text.encode())
            prefix = f"telemetry/legs/{leg:03d}"
            snapshot["files"][prefix + "/observations.csv"] = text
            details = json.loads(snapshot["files"][prefix + "/manifest.json"])
            details["checksum"]["observations.csv"] = hashlib.sha256(
                text.encode()
            ).hexdigest()
            details["synthetic_size_fixture"] = {
                "hours": 18,
                "channels": 13,
                "cadence_seconds": 1,
            }
            snapshot["files"][prefix + "/manifest.json"] = json.dumps(
                details, sort_keys=True
            )
            telemetry_manifest["legs"][leg - 1]["checksum"] = details["checksum"]
            csv.close()
            del text
        snapshot["files"]["telemetry/manifest.json"] = json.dumps(
            telemetry_manifest, sort_keys=True
        )
        assert 100 * MIB < total < 256 * MIB, total
        # Run the production persistence and additive ZIP assembly code with a
        # substantial frozen snapshot, not a stand-in serializer.
        store = PreparationStore(SlideStore(directory / "slides.sqlite3"))
        job = ExportPreparation(
            id="large",
            mission_id="synthetic-large-archive-transfer",
            state="queued",
            fingerprint="size-probe",
            queued_at=0,
            deadline=600,
        )
        store.write(job, archive=snapshot)
        database = directory / "slides.sqlite3"
        first_size = database.stat().st_size
        # Quota failures use the same substantial live DB and must leave its
        # acknowledged snapshot intact, with no falsely queued partial job.
        from app.mission.package import preparation_store as limits

        original_limits = (
            limits.MAX_ARCHIVE_STORAGE_BYTES,
            limits.MAX_ARCHIVE_SNAPSHOT_BYTES,
        )
        rejected = job.model_copy(update={"id": "rejected"})
        try:
            limits.MAX_ARCHIVE_STORAGE_BYTES = 0
            try:
                store.write(rejected, archive={"files": {"a": "x"}})
                raise AssertionError("Storage quota accepted a partial export")
            except RuntimeError:
                pass
            limits.MAX_ARCHIVE_STORAGE_BYTES = original_limits[0]
            limits.MAX_ARCHIVE_SNAPSHOT_BYTES = 1024
            try:
                store.write(rejected, archive={"files": {"a": "x" * 1024}})
                raise AssertionError("Snapshot quota accepted a partial export")
            except RuntimeError:
                pass
            try:
                store.read(job.mission_id, rejected.id)
                raise AssertionError("Rejected snapshot left a queued job")
            except KeyError:
                pass
        finally:
            limits.MAX_ARCHIVE_STORAGE_BYTES, limits.MAX_ARCHIVE_SNAPSHOT_BYTES = (
                original_limits
            )
        result.update(
            storageQuotaRejectionAtomic=True, snapshotQuotaRejectionAtomic=True
        )
        frozen = store.archive(job.id)
        assert frozen == snapshot
        del snapshot
        gc.collect()
        with append_archive(
            core, frozen, planning_fingerprint="size-probe", cancel=None
        ) as stream:
            compressed = directory / "large-export.zip"
            with compressed.open("wb") as target:
                while block := stream.read(MIB):
                    target.write(block)
        del frozen
        gc.collect()
        # ZIP compression method is not an import contract. Preserve the exact
        # members using STORE to exercise a valid telemetry-rich ZIP >100 MiB.
        large = directory / "large-transfer.zip"
        with zipfile.ZipFile(compressed) as source, zipfile.ZipFile(
            large, "w"
        ) as target:
            for entry in source.infolist():
                with source.open(entry) as incoming, target.open(
                    entry.filename, "w"
                ) as outgoing:
                    while block := incoming.read(MIB):
                        outgoing.write(block)
            manifest = json.loads(source.read("manifest.json"))
            for name, digest in manifest["archive_components"]["checksums"].items():
                identity = hashlib.sha256()
                with source.open(name) as stream:
                    while block := stream.read(MIB):
                        identity.update(block)
                assert identity.hexdigest() == digest
        assert large.stat().st_size > 100 * MIB
        # Release and reuse storage, verifying SQLite does not grow each cycle.
        store.discard_archive(job.id)
        assert store.archive(job.id) is None
        store.write(job, archive={"files": {"a": "x" * MIB}})
        store.discard_archive(job.id)
        assert database.stat().st_size <= first_size + MIB
        # Exercise production expiry after the substantial allocation: the
        # snapshot and artifact disappear while the SQLite pages remain reusable.
        from app.mission.package.preparation import ExportPreparationService

        with store.cache.connection() as db:
            db.execute("DELETE FROM export_jobs")
        service = ExportPreparationService(
            None, None, enabled=False, cache=store.cache, clock=lambda: 1000
        )
        try:
            service.close()
            expiring = job.model_copy(
                update={"id": "expiry", "state": "ready", "expires_at": 999}
            )
            store.write(expiring, archive={"files": {"a": "x" * MIB}})
            service.path("expiry").write_bytes(b"PK-expiry-fixture")
            assert service.status(job.mission_id, "expiry").state == "expired"
            assert store.archive("expiry") is None
            assert not service.path("expiry").exists()
        finally:
            service.close()
        result["expiredSnapshotAndArtifactRemoved"] = True
        result.update(
            rows=count,
            expandedTelemetryBytes=total,
            preparedZipBytes=compressed.stat().st_size,
            largeTransferZipBytes=large.stat().st_size,
            databasePeakBytes=first_size,
            databaseAfterReleaseBytes=database.stat().st_size,
            liveSnapshotsAfterRelease=0,
        )
        before_hwm = hwm()
        with httpx.Client(
            base_url="http://mission-planner", timeout=600
        ) as nginx, httpx.Client(
            base_url="http://import-destination:8000", timeout=600
        ) as destination:
            destination_before, source_before = journal(destination), journal(nginx)
            for client in (destination, nginx):
                response = upload(client, large)
                response.raise_for_status()
                imported = response.json()
                assert (
                    imported["success"]
                    and imported["leg_count"] == 2
                    and imported["routes_imported"] >= 1
                )
            assert journal(destination) == destination_before
            assert journal(nginx) == source_before
            # Sparse self-extracting-style ZIP preambles are boundary probes,
            # separate from the realistic long-duration CSV fixture above.
            core_bytes = core.getvalue()
            boundaries = []
            cap = 2 * 1024 * MIB
            for size, expected, layer in (
                (cap, 200, None),
                (cap + 1, 413, "application"),
                (cap + 2 * MIB, 413, "mission-planner-nginx"),
            ):
                boundary = directory / "boundary.zip"
                with boundary.open("wb") as stream:
                    stream.seek(size - len(core_bytes))
                    stream.write(core_bytes)
                response = upload(nginx, boundary)
                assert response.status_code == expected, (
                    size,
                    response.status_code,
                    response.text,
                )
                if layer:
                    assert response.json()["detail"]["layer"] == layer
                    assert response.json()["detail"]["max_bytes"] == cap
                boundaries.append(
                    {"zipBytes": size, "status": response.status_code, "layer": layer}
                )
                boundary.unlink()
            assert journal(nginx) == source_before
            result.update(
                cleanDestinationJournalUnchanged=True,
                sourceJournalUnchanged=True,
                directAndProductionNginxImport=True,
                uploadBoundaries=boundaries,
            )
        result.update(
            backendHighWaterBeforeBytes=before_hwm,
            backendHighWaterAfterBytes=hwm(),
            probePeakRssBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            elapsedSeconds=round(time.monotonic() - started, 2),
        )
    result["temporaryFilesRemoved"] = not directory.exists()
    (ROOT / "archive-limits.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    run()
