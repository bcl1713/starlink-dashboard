"""Pinned active cursors and bounded SQLite TEXT reads for sealed evidence."""

import codecs
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from app.mission.package.archive_errors import ArchiveCapacityError

BLOCK = 65536
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_METADATA_BYTES = 8 * 1024 * 1024


class JsonReader:
    """Frame the known capture object; decode one metadata value or sample at a time."""

    def __init__(self, stream, check):
        self.stream, self.check = stream, check
        self.buffer, self.eof = "", False
        self.utf8 = codecs.getincrementaldecoder("utf-8")()
        self.decoder = json.JSONDecoder()

    def fill(self):
        self.check()
        chunk = self.stream.read(BLOCK)
        self.eof = not chunk
        self.buffer += self.utf8.decode(chunk, final=self.eof)

    def peek(self):
        self.buffer = self.buffer.lstrip()
        while not self.buffer and not self.eof:
            self.fill()
            self.buffer = self.buffer.lstrip()
        return self.buffer[:1]

    def token(self, token):
        if self.peek() != token:
            raise ValueError("Invalid or truncated telemetry capture JSON")
        self.buffer = self.buffer[1:]

    def value(self):
        self.peek()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer)
            except json.JSONDecodeError as error:
                if self.eof:
                    raise ValueError(
                        "Invalid or truncated telemetry capture JSON"
                    ) from error
                if len(self.buffer.encode("utf-8")) > MAX_RECORD_BYTES:
                    raise ArchiveCapacityError("telemetry-record", MAX_RECORD_BYTES)
                self.fill()
                continue
            if end == len(self.buffer) and not self.eof:
                self.fill()
                continue
            if len(self.buffer[:end].encode("utf-8")) > MAX_RECORD_BYTES:
                raise ArchiveCapacityError("telemetry-record", MAX_RECORD_BYTES)
            self.buffer = self.buffer[end:]
            return value

    def fields(self):
        self.token("{")
        first = True
        while self.peek() != "}":
            if not first:
                self.token(",")
            first = False
            key = self.value()
            if not isinstance(key, str):
                raise TypeError("Capture object key is not text")
            self.token(":")
            if key == "samples":
                self.token("[")
                initial = True
                while self.peek() != "]":
                    if not initial:
                        self.token(",")
                    initial = False
                    yield "samples.item", self.value()
                self.token("]")
            else:
                yield key, self.value()
        self.token("}")
        if self.peek():
            raise ValueError("Unexpected data after telemetry capture")


def read_capture(db, rowid, check):
    metadata, size = {}, 0
    with db.blobopen("captures", "payload", rowid, readonly=True) as stream:
        for key, value in JsonReader(stream, check).fields():
            if key != "samples.item":
                size += len(json.dumps(value, ensure_ascii=False).encode())
                if size > MAX_METADATA_BYTES:
                    raise ArchiveCapacityError("telemetry-metadata", MAX_METADATA_BYTES)
                metadata[key] = value
    return metadata


def iter_capture_samples(db, rowid, check):
    with db.blobopen("captures", "payload", rowid, readonly=True) as stream:
        for key, value in JsonReader(stream, check).fields():
            if key == "samples.item":
                check()
                yield value


def active_samples(db, metadata, check):
    start = datetime.fromisoformat(metadata["start"]).timestamp()
    end = datetime.fromisoformat(metadata["available_until"]).timestamp()
    cursor = db.execute(
        "SELECT ts,metric,labels,value,observed_at FROM samples WHERE ts>=? AND ts<=? AND mode='live' ORDER BY ts,metric,labels",
        (start, end),
    )
    try:
        for stamp, metric, labels, value, observed in cursor:
            check()
            if len(labels.encode()) > MAX_RECORD_BYTES:
                raise ArchiveCapacityError("telemetry-record", MAX_RECORD_BYTES)
            yield {
                "timestamp": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                "metric": metric,
                "labels": json.loads(labels),
                "value": value,
                "observed_at": observed,
            }
    finally:
        cursor.close()


@contextmanager
def stream_captures(archive, mission_id, legs, *, check=lambda: None):
    with archive.ledger.connect() as db:
        db.execute("BEGIN")

        def captures():
            for leg in legs:
                check()
                row = db.execute(
                    "SELECT c.rowid FROM capture_heads h JOIN captures c ON c.mission=h.mission AND c.leg=h.leg AND c.revision=h.revision WHERE h.mission=? AND h.leg=?",
                    (mission_id, leg),
                ).fetchone()
                if row is None:
                    yield {
                        "mission_id": mission_id,
                        "leg_id": leg,
                        "revision": "unavailable",
                        "source_mode": "live",
                        "state": "unavailable",
                        "complete": False,
                        "start": None,
                        "end": None,
                        "events": [],
                        "gaps": [{"reason": "leg_not_recorded"}],
                        "samples": iter(()),
                    }
                    continue
                metadata = read_capture(db, row[0], check)
                samples = (
                    iter_capture_samples(db, row[0], check)
                    if metadata["state"] == "sealed"
                    else active_samples(db, metadata, check)
                )
                try:
                    yield metadata | {"samples": samples}
                finally:
                    samples.close()

        values = captures()
        try:
            yield values
        finally:
            values.close()
