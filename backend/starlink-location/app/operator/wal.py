"""Conservative WAL preflight before SQLite can discard malformed frames.

Call only under exclusive maintenance admission. This detects malformed bytes,
not replacement with an otherwise valid older database/WAL or complete removal.
"""

import struct
import time
from pathlib import Path

from .errors import OperatorError


def _checksum(data, state, endian):
    first, second = state
    for left, right in struct.iter_unpack(endian + "II", data):
        first = (first + left + second) & 0xFFFFFFFF
        second = (second + right + first) & 0xFFFFFFFF
    return first, second


def validate_wal(database):
    path = Path(str(database) + "-wal")
    if not path.exists() or path.stat().st_size == 0:
        return
    deadline = time.monotonic() + 2
    with path.open("rb") as source:
        header = source.read(32)
        if len(header) != 32:
            raise OperatorError("store_corrupt")
        magic, version, size = struct.unpack(">III", header[:12])
        if (
            magic not in (0x377F0682, 0x377F0683)
            or version != 3007000
            or size < 512
            or size > 65536
            or size & (size - 1)
        ):
            raise OperatorError("store_corrupt")
        if (path.stat().st_size - 32) % (24 + size):
            raise OperatorError("store_corrupt")
        endian = "<" if magic == 0x377F0682 else ">"
        state = _checksum(header[:24], (0, 0), endian)
        if state != struct.unpack(">II", header[24:32]):
            raise OperatorError("store_corrupt")
        while frame := source.read(24 + size):
            if time.monotonic() >= deadline:
                raise OperatorError("maintenance_timeout", retryable=True)
            # A reused WAL can retain complete frames from a previous salt.
            if frame[8:16] != header[16:24]:
                break
            if struct.unpack(">I", frame[:4])[0] == 0:
                raise OperatorError("store_corrupt")
            state = _checksum(frame[:8] + frame[24:], state, endian)
            if state != struct.unpack(">II", frame[16:24]):
                raise OperatorError("store_corrupt")
