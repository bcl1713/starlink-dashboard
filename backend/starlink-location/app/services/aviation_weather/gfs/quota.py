"""Process-shared scientific quotas with crash-recoverable reservation locks."""

import fcntl
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DAILY_BYTES = 5 * 1024**3


class GfsQuota:
    def __init__(self, root: Path, *, clock=time.time):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self._handles = {}

    @contextmanager
    def _locked(self):
        with (self.root / ".budget.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root / "budget.json"
            now = self.clock()
            try:
                data = json.loads(path.read_bytes())
            except FileNotFoundError:
                data = {
                    "last": now,
                    "day": int(now // 86400),
                    "bytes": 0,
                    "attempts": [],
                    "tokens": {},
                }
            for token in tuple(data["tokens"]):
                if not re.fullmatch(r"[a-f0-9]{32}", token):
                    raise ValueError("Invalid budget reservation")
                if token in self._handles:
                    continue
                with (self.root / token).open("a") as owner:
                    try:
                        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    # A crashed owner may have received bytes immediately before
                    # persisting a charge. Account for every uncharged byte.
                    if int(now // 86400) > data["day"]:
                        data["day"], data["bytes"] = int(now // 86400), 0
                    data["bytes"] += data["tokens"].pop(token)
                    (self.root / token).unlink(missing_ok=True)
            try:
                yield data, now
            finally:
                stage = path.with_suffix(".partial")
                with stage.open("w") as stream:
                    json.dump(data, stream, sort_keys=True, allow_nan=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                stage.replace(path)
                directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)

    def _admit_clock(self, data, now):
        if now < data["last"]:
            raise ValueError("Clock rollback invalidates acquisition")
        if int(now // 86400) > data["day"]:
            data["day"], data["bytes"] = int(now // 86400), 0
        data["last"] = now

    def attempt(self):
        with self._locked() as (data, now):
            self._admit_clock(data, now)
            data["attempts"] = [
                instant for instant in data["attempts"] if instant > now - 60
            ]
            if len(data["attempts"]) >= 20:
                raise ValueError("Scientific request budget exhausted")
            data["attempts"].append(now)

    def reserve(self, bytes_: int) -> str:
        if type(bytes_) is not int or not 0 <= bytes_ <= 32 * 1024**2:
            raise ValueError("Invalid scientific reservation")
        with self._locked() as (data, now):
            self._admit_clock(data, now)
            if (
                len(data["tokens"]) >= 2
                or data["bytes"] + sum(data["tokens"].values()) + bytes_ > DAILY_BYTES
            ):
                raise ValueError("Scientific acquisition budget exhausted")
            token = uuid.uuid4().hex
            owner = (self.root / token).open("x")
            fcntl.flock(owner, fcntl.LOCK_EX)
            self._handles[token] = owner
            data["tokens"][token] = bytes_
            return token

    def charge(self, token: str, received_bytes: int) -> None:
        with self._locked() as (data, now):
            if (
                token not in self._handles
                or type(received_bytes) is not int
                or received_bytes < 0
            ):
                raise ValueError("Invalid transfer charge")
            rollback = now < data["last"]
            if not rollback:
                self._admit_clock(data, now)
            remaining = data["tokens"][token]
            data["tokens"][token] = max(0, remaining - received_bytes)
            data["bytes"] += received_bytes
            if rollback or received_bytes > remaining or data["bytes"] > DAILY_BYTES:
                raise ValueError("Scientific transfer exceeds reservation")

    def release(self, token: str) -> None:
        with self._locked() as (data, _):
            data["tokens"].pop(token, None)
            owner = self._handles.pop(token, None)
            if owner:
                owner.close()
                (self.root / token).unlink(missing_ok=True)

    def close(self):
        for token in tuple(self._handles):
            self.release(token)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
