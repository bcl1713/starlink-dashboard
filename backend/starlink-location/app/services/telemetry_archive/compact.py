"""A disposable bounded disk index, rather than a whole-history series mapping."""

import hashlib
import json
import sqlite3

from app.mission.package.archive_errors import ArchiveCapacityError


class SeriesIndex:
    def __init__(self, path, max_bytes):
        self.path = path
        self.max_bytes = max_bytes
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
        except BaseException:
            self.db.close()
            self.path.unlink(missing_ok=True)
            raise

    def identify(self, sample):
        labels = json.dumps(sample["labels"], sort_keys=True)
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
        return series

    def rows(self):
        yield from self.db.execute("SELECT id,metric,labels FROM series ORDER BY id")

    def close(self):
        self.db.close()
        self.path.unlink(missing_ok=True)
