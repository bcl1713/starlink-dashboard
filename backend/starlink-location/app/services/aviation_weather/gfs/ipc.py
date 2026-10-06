"""Small revisioned mailbox shared by API readers and the scientific worker."""

import fcntl
import re
import time
from pathlib import Path

from .store import atomic_json, control_lock, read_json


class GfsMailbox:
    def __init__(self, root: Path, settings, *, monotonic=time.monotonic):
        self.root, self.settings = Path(root), settings
        self.root.mkdir(parents=True, exist_ok=True)
        self.monotonic = monotonic
        self._deadlines = {}

    def _demand(self):
        try:
            return read_json(self.root / "demand.json")
        except FileNotFoundError:
            return {
                "revision": self.settings.get().revision,
                "last_ms": 0,
                "owners": {},
            }

    def _save(self, data):
        atomic_json(self.root / "demand.json", data)

    def observe_clock_locked(self, now_ms: int):
        # All catalog and payload admission shares this durable high-water
        # mark. Callers hold the control lock, including ASGI's second check.
        data = self._demand()
        if now_ms < data["last_ms"]:
            if data["owners"]:
                data["owners"] = {}
                self._save(data)
            raise ValueError("Clock rollback invalidates scientific admission")
        if now_ms > data["last_ms"]:
            data["last_ms"] = now_ms
            self._save(data)
        return data

    def renew(self, owner: str, settings, now_ms: int) -> None:
        if not re.fullmatch(r"[a-f0-9]{32}", owner):
            raise ValueError("Invalid API startup identity")
        with control_lock(self.root, timeout=1):
            current = self.settings.get()
            data = self.observe_clock_locked(now_ms)
            if settings != current:
                raise ValueError("Obsolete scientific settings revision")
            if data["revision"] != settings.revision:
                data["revision"], data["owners"] = settings.revision, {}
            data["owners"] = {
                key: value
                for key, value in data["owners"].items()
                if value["expires_ms"] > now_ms
            }
            if owner not in data["owners"] and len(data["owners"]) >= 16:
                raise ValueError("Scientific reader demand is saturated")
            data["last_ms"] = now_ms
            if settings.winds or settings.temperature:
                data["owners"][owner] = {
                    "renewed_ms": now_ms,
                    "expires_ms": now_ms + 120000,
                }
            else:
                data["owners"].pop(owner, None)
            self._save(data)

    def withdraw(self, owner: str) -> None:
        with control_lock(self.root, timeout=1):
            data = self._demand()
            data["owners"].pop(owner, None)
            self._save(data)

    def invalidate_locked(self, revision: int) -> None:
        data = self._demand()
        data["revision"], data["owners"] = revision, {}
        self._save(data)

    def invalidate(self, revision: int) -> None:
        with control_lock(self.root, timeout=1):
            self.invalidate_locked(revision)

    def current(self, now_ms: int):
        with control_lock(self.root, timeout=1):
            return self.current_locked(now_ms)

    def current_locked(self, now_ms: int):
        settings, data = self.settings.get(), self._demand()
        if now_ms < data["last_ms"]:
            data["owners"] = {}
            self._save(data)
            return None
        if settings.revision != data["revision"] or not (
            settings.winds or settings.temperature
        ):
            return None
        alive = False
        self._deadlines = {
            key: value
            for key, value in self._deadlines.items()
            if key in data["owners"]
        }
        for owner, value in data["owners"].items():
            recorded = self._deadlines.get(owner)
            if recorded is None or recorded[0] != value["renewed_ms"]:
                remaining = max(0, min(120, (value["expires_ms"] - now_ms) / 1000))
                recorded = value["renewed_ms"], self.monotonic() + remaining
                self._deadlines[owner] = recorded
            alive |= (
                value["renewed_ms"] <= now_ms < value["expires_ms"]
                and self.monotonic() < recorded[1]
            )
        return settings if alive else None

    def worker_present(self):
        # Heartbeat loss is insufficient proof of absence. Decoder children
        # inherit this flock's open-file description through their lifetime.
        with (self.root / "worker.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            return False

    def worker_started(self, owner, now_ms):
        with control_lock(self.root, timeout=1):
            atomic_json(
                self.root / "worker.json", {"owner": owner, "started_ms": now_ms}
            )

    def heartbeat(self, revision, owner, now_ms):
        with control_lock(self.root, timeout=1):
            try:
                identity = read_json(self.root / "worker.json")
            except FileNotFoundError:
                identity = {"owner": owner, "started_ms": now_ms}
                atomic_json(self.root / "worker.json", identity)
            if identity["owner"] != owner:
                raise ValueError("Obsolete scientific worker identity")
            atomic_json(
                self.root / "ack.json",
                {"revision": revision, "owner": owner, "heartbeat_ms": now_ms},
            )

    def acknowledged(self, revision: int) -> bool:
        if not self.worker_present():
            return True
        try:
            ack = read_json(self.root / "ack.json")
            identity = read_json(self.root / "worker.json")
            return ack["revision"] == revision and ack["owner"] == identity["owner"]
        except (FileNotFoundError, ValueError, KeyError):
            return False

    def healthy(self, now_ms: int) -> bool:
        if not self.worker_present():
            return False
        try:
            ack = read_json(self.root / "ack.json")
            identity = read_json(self.root / "worker.json")
            return (
                ack["owner"] == identity["owner"]
                and 0 <= now_ms - ack["heartbeat_ms"] <= 15000
            )
        except (FileNotFoundError, ValueError, KeyError):
            return False
