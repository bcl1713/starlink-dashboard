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
        current_salt = header[16:24]
        current_generation = int.from_bytes(current_salt[:4], "big")
        previous_salt, previous_age = current_salt, 0
        while frame := source.read(24 + size):
            if time.monotonic() >= deadline:
                raise OperatorError("maintenance_timeout", retryable=True)
            if struct.unpack(">I", frame[:4])[0] == 0:
                raise OperatorError("store_corrupt")
            candidate = _checksum(frame[:8] + frame[24:], state, endian)
            stored = struct.unpack(">II", frame[16:24])
            salt = frame[8:16]
            if salt == previous_salt:
                if candidate != stored:
                    raise OperatorError("store_corrupt")
            else:
                # Salts are NOT covered by frame checksums. A salt mismatch
                # which still continues the preceding chain is damaged active
                # data, not evidence that SQLite may safely discard the suffix.
                if candidate == stored:
                    raise OperatorError("store_corrupt")
                age = (
                    current_generation - int.from_bytes(salt[:4], "big")
                ) & 0xFFFFFFFF
                # Reuse overwrites a prefix. Surviving generations must only get
                # older as offsets increase, never return to the current epoch.
                if not previous_age < age < 0x80000000:
                    raise OperatorError("store_corrupt")
                previous_age = age
                previous_salt = salt
            if salt == current_salt and previous_age:
                raise OperatorError("store_corrupt")
            # At an older-generation boundary its predecessor was overwritten;
            # seed from its stored checksum, then validate its entire run. Do
            # not stop scanning: active frames after a false boundary are damage.
            state = stored
