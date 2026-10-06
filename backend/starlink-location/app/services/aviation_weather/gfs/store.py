"""Immutable, bounded artifacts with shared publication and reader locks."""

import fcntl
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.models.aviation_grid import GfsSelection, GridCandidate, GridDescriptor

STAGING_BYTES = 1024**3
PUBLISHED_BYTES = 5 * 1024**3 // 2
RESERVE_BYTES = 512 * 1024**2


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path, value):
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    with path.open("rb") as stream:
        body = stream.read(1024**2 + 1)
    if len(body) > 1024**2:
        raise ValueError("Oversized private metadata")
    return json.loads(body)


@contextmanager
def control_lock(mailbox):
    with (mailbox / ".control.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def occupied(path):
    seen = set()
    size = 0
    for entry in path.rglob("*"):
        stat = entry.lstat()
        if entry.is_symlink():
            raise ValueError("Symlink in private scientific storage")
        key = stat.st_dev, stat.st_ino
        if entry.is_file() and key not in seen:
            size += stat.st_size
            seen.add(key)
    return size


class GfsProductStore:
    def __init__(
        self, root: Path, mailbox: Path, settings, *, readonly=False, clock=time.time
    ):
        self.root, self.mailbox, self.settings = Path(root), Path(mailbox), settings
        self.clock = clock
        self.mailbox.mkdir(parents=True, exist_ok=True)
        (self.mailbox / "leases").mkdir(exist_ok=True)
        if not readonly:
            for path in (self.root / "staging", self.root / "products"):
                path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def staging(self):
        # Recovery cannot race a live decoder; the inode remains persistent.
        with (self.mailbox / ".staging.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for abandoned in (self.root / "staging").iterdir():
                if abandoned.is_dir() and re.fullmatch(r"[a-f0-9]{32}", abandoned.name):
                    shutil.rmtree(abandoned)
            if shutil.disk_usage(self.root).free < STAGING_BYTES + RESERVE_BYTES:
                raise ValueError("Scientific staging lacks reserved space")
            path = self.root / "staging" / uuid.uuid4().hex
            path.mkdir()
            try:
                yield path
            finally:
                shutil.rmtree(path)

    def _descriptor(self, instance):
        if not re.fullmatch(r"[a-f0-9]{64}", instance):
            raise ValueError("Invalid scientific instance")
        return GridDescriptor.model_validate(
            read_json(self.root / "products" / instance / "grid.json")
        )

    def _validate_candidate(self, candidate):
        descriptor = GridDescriptor.model_validate_json(
            (candidate.directory / "grid.json").read_bytes()
        )
        if descriptor != candidate.descriptor:
            raise ValueError("Candidate descriptor mismatch")
        for name, buffer in descriptor.buffers.items():
            path = candidate.directory / f"{name}.bin"
            if path.is_symlink() or path.stat().st_size != buffer.byte_length:
                raise ValueError("Candidate buffer size mismatch")
            if hashlib.sha256(path.read_bytes()).hexdigest() != buffer.sha256:
                raise ValueError("Candidate buffer hash mismatch")
        return occupied(candidate.directory)

    def publish(self, candidate: GridCandidate, revision: int) -> None:
        size = self._validate_candidate(candidate)
        admission = read_json(candidate.directory / "admission.json")
        with control_lock(self.mailbox):
            settings = self.settings.get()
            now = int(self.clock() * 1000)
            target = now + settings.gfs_selection.horizon_hours * 3600000
            if (
                settings.revision != revision
                or not (settings.winds or settings.temperature)
                or admission["selection"] != settings.gfs_selection.model_dump()
                or not admission["target_from_ms"]
                <= target
                <= admission["target_to_ms"]
                or not candidate.descriptor.run_at_ms <= now + 60000
                or now >= candidate.descriptor.run_at_ms + 18 * 3600000
                or candidate.descriptor.generated_at_ms
                >= candidate.descriptor.run_at_ms + 18 * 3600000
                or settings.gfs_selection.pressure_pa
                != candidate.descriptor.vertical.pressure_pa
            ):
                raise ValueError("Scientific candidate belongs to obsolete settings")
            if size > STAGING_BYTES or occupied(self.root / "staging") > STAGING_BYTES:
                raise ValueError("Scientific staging budget exceeded")
            runs = {
                self._descriptor(path.name).run_at_ms
                for path in (self.root / "products").iterdir()
                if path.is_dir() and re.fullmatch(r"[a-f0-9]{64}", path.name)
            }
            if candidate.descriptor.run_at_ms not in runs and len(runs) >= 2:
                raise ValueError("Scientific retention already holds two runs")
            if (
                occupied(self.root / "products") + size + 16384 > PUBLISHED_BYTES
                or shutil.disk_usage(self.root).free < size + RESERVE_BYTES
            ):
                raise ValueError("Scientific publication budget exceeded")
            instances = {}
            for kind in ("winds", "temperature"):
                descriptor = candidate.descriptor.model_dump(by_alias=True)
                product = hashlib.sha256(
                    canonical({"base": descriptor["product_id"], "kind": kind})
                ).hexdigest()
                instance = hashlib.sha256(
                    canonical({"base": descriptor["instance_id"], "kind": kind})
                ).hexdigest()
                descriptor.update(product_id=product, instance_id=instance)
                for name, buffer in descriptor["buffers"].items():
                    buffer["path"] = (
                        f"/api/aviation-weather/v1/products/{instance}/{name}.bin"
                    )
                descriptor = GridDescriptor.model_validate(descriptor)
                destination = self.root / "products" / instance
                if not destination.exists():
                    temporary = candidate.directory.parent / uuid.uuid4().hex
                    try:
                        shutil.copytree(
                            candidate.directory, temporary, copy_function=os.link
                        )
                        # Unlink before rewrite: never mutate a shared inode.
                        (temporary / "grid.json").unlink()
                        atomic_json(
                            temporary / "grid.json",
                            descriptor.model_dump(by_alias=True),
                        )
                        fsync_directory(temporary)
                        temporary.replace(destination)
                        fsync_directory(destination.parent)
                    finally:
                        if temporary.exists():
                            shutil.rmtree(temporary)
                else:
                    existing = self._descriptor(instance)
                    if any(
                        existing.buffers[name].sha256 != buffer.sha256
                        for name, buffer in descriptor.buffers.items()
                    ):
                        raise ValueError("Immutable scientific instance collision")
                instances[kind] = instance
            atomic_json(
                self.root / "current.json",
                {"revision": revision, **admission, "instances": instances},
            )

    def read_current(
        self, selection: GfsSelection, now_ms: int
    ) -> tuple[GridDescriptor, ...]:
        try:
            pointer = read_json(self.root / "current.json")
            if pointer["selection"] != selection.model_dump():
                return ()
            target = now_ms + selection.horizon_hours * 3600000
            if not pointer["target_from_ms"] <= target <= pointer["target_to_ms"]:
                return ()
            descriptors = tuple(
                self._descriptor(pointer["instances"][kind])
                for kind in ("winds", "temperature")
            )
            if any(
                not descriptor.run_at_ms <= now_ms + 60000
                or now_ms >= descriptor.run_at_ms + 18 * 3600000
                for descriptor in descriptors
            ):
                return ()
            if any(
                not descriptor.run_at_ms
                <= now_ms + selection.horizon_hours * 3600000
                <= descriptor.run_at_ms + 48 * 3600000
                for descriptor in descriptors
            ):
                return ()
            return descriptors
        except (FileNotFoundError, KeyError, ValueError, TypeError):
            return ()

    @contextmanager
    def lease(self, instance):
        if not re.fullmatch(r"[a-f0-9]{64}", instance):
            raise ValueError("Invalid scientific instance")
        with (self.mailbox / "leases" / instance).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            yield self._descriptor(instance)

    def prune(self, now_ms: int) -> None:
        with control_lock(self.mailbox):
            entries = []
            for path in (self.root / "products").iterdir():
                if path.is_dir() and re.fullmatch(r"[a-f0-9]{64}", path.name):
                    try:
                        entries.append((path, self._descriptor(path.name)))
                    except (ValueError, FileNotFoundError):
                        continue
            retained_runs = sorted(
                {descriptor.run_at_ms for _, descriptor in entries}, reverse=True
            )[:2]
            admitted = {
                descriptor.instance_id
                for descriptor in self.read_current(
                    self.settings.get().gfs_selection, now_ms
                )
            }
            for path, descriptor in entries:
                expired = now_ms >= descriptor.run_at_ms + 18 * 3600000
                if (
                    not expired
                    and descriptor.run_at_ms in retained_runs
                    and path.name in admitted
                ):
                    continue
                with (self.mailbox / "leases" / path.name).open("a") as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    shutil.rmtree(path)
            fsync_directory(self.root / "products")
