"""A disposable bounded disk index, rather than a whole-history series mapping."""

import hashlib
import json
import sqlite3
from collections import OrderedDict

from app.mission.package.archive_errors import ArchiveCapacityError


class SeriesIndex:
    def __init__(self, path, max_bytes):
        self.path = path
        self.max_bytes = max_bytes
        self.series_cache = OrderedDict()
        self.db = sqlite3.connect(path)
        try:
            self.db.execute("PRAGMA journal_mode=OFF")
            self.db.execute("PRAGMA synchronous=OFF")
            self.db.execute("PRAGMA cache_size=-2048")
            self.db.execute("PRAGMA temp_store=FILE")
            page = self.db.execute("PRAGMA page_size").fetchone()[0]
            self.db.execute(f"PRAGMA max_page_count={max(1, max_bytes // page)}")
            self.db.execute(
                "CREATE TABLE series (id TEXT PRIMARY KEY, metric TEXT, labels TEXT)"
            )
            self.db.execute(
                "CREATE TABLE observations (ts REAL,metric TEXT,labels TEXT,stamp TEXT,value REAL,observed TEXT,PRIMARY KEY(ts,metric,labels)) WITHOUT ROWID"
            )
        except BaseException:
            self.db.close()
            self.path.unlink(missing_ok=True)
            raise

    def identify(self, sample):
        labels = json.dumps(sample["labels"], sort_keys=True)
        key = sample["metric"], labels
        if key in self.series_cache:
            self.series_cache.move_to_end(key)
            return self.series_cache[key]
        identity = json.dumps([sample["metric"], labels], ensure_ascii=True)
        series = hashlib.sha256(identity.encode()).hexdigest()
        try:
            self.db.execute(
                "INSERT OR IGNORE INTO series VALUES (?,?,?)",
                (series, sample["metric"], labels),
            )
        except sqlite3.OperationalError as error:
            if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                raise ArchiveCapacityError("compact-index", self.max_bytes) from error
            raise
        # Keep at most 1 MiB of label text. High-cardinality/large identities
        # remain in the bounded disk index, without growing a history-sized map.
        if len(labels) <= 1024:
            self.series_cache[key] = series
            if len(self.series_cache) > 1024:
                self.series_cache.popitem(last=False)
        return series

    def rows(self):
        yield from self.db.execute("SELECT id,metric,labels FROM series ORDER BY id")

    def add_observation(self, sample):
        from datetime import datetime

        try:
            self.db.execute(
                "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)",
                (
                    datetime.fromisoformat(sample["timestamp"]).timestamp(),
                    sample["metric"],
                    json.dumps(sample["labels"], sort_keys=True),
                    sample["timestamp"],
                    sample["value"],
                    sample.get("observed_at"),
                ),
            )
        except sqlite3.OperationalError as error:
            if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                raise ArchiveCapacityError(
                    "retained-observation-index", self.max_bytes
                ) from error
            raise

    def observations(self):
        cursor = self.db.execute(
            "SELECT stamp,metric,labels,value,observed FROM observations ORDER BY ts,metric,labels"
        )
        try:
            for stamp, metric, labels, value, observed in cursor:
                yield {
                    "timestamp": stamp,
                    "metric": metric,
                    "labels": json.loads(labels),
                    "value": value,
                    "observed_at": observed,
                }
        finally:
            cursor.close()

    def close(self):
        self.series_cache.clear()
        self.db.close()
        self.path.unlink(missing_ok=True)
