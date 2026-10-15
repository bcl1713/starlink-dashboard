"""Atomic aggregate accounting shared by capture writers in one directory."""

import fcntl
import threading
from contextlib import contextmanager
from pathlib import Path

LIMIT = 1024**3
_LOCKS = {}
_REGISTRY = threading.Lock()


@contextmanager
def locked(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with _REGISTRY:
        lock = _LOCKS.setdefault(root, threading.RLock())
    with lock, (root / ".storage.lock").open("a") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        try:
            yield root
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


def write_chunk(root, output, chunk, limit=LIMIT):
    with locked(root) as directory:
        used = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
        if used + len(chunk) > limit:
            raise ValueError("download storage limit")
        output.write(chunk)
        output.flush()


def publish(temporary, target, root):
    with locked(root):
        temporary.replace(target)


def discard(path, root):
    with locked(root):
        path.unlink(missing_ok=True)


def atomic_write(path, data, *, root, limit=LIMIT):
    temporary = path.with_suffix(path.suffix + ".partial")
    try:
        with temporary.open("wb") as output:
            write_chunk(root, output, data, limit)
        publish(temporary, path, root)
    finally:
        discard(temporary, root)
