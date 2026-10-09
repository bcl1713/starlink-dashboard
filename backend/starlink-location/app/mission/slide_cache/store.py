"""Transactional desired revisions and their assembly-ready bytes."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


class SlideStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS slides (
                mission TEXT, leg TEXT, fingerprint TEXT, token TEXT, state TEXT,
                inputs BLOB, snapshot BLOB, pdf BLOB, evidence BLOB, warning TEXT,
                PRIMARY KEY (mission, leg))""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def request(self, mission, leg, fingerprint, inputs, *, retry=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT * FROM slides WHERE mission=? AND leg=?", (mission, leg)
            ).fetchone()
            if (
                old
                and old["fingerprint"] == fingerprint
                and old["state"] != "dirty"
                and not (retry and old["state"] == "failed")
            ):
                return old["token"]
            token = uuid4().hex
            db.execute(
                "INSERT OR REPLACE INTO slides VALUES (?,?,?,?,?,?,NULL,NULL,NULL,NULL)",
                (mission, leg, fingerprint, token, "queued", inputs),
            )
            return token

    def invalidate(self, mission, legs):
        with self.connection() as db:
            for leg in legs:
                db.execute(
                    "UPDATE slides SET state='dirty', token=?, snapshot=NULL, pdf=NULL, evidence=NULL WHERE mission=? AND leg=?",
                    (uuid4().hex, mission, leg),
                )

    def remove_except(self, mission, legs):
        with self.connection() as db:
            rows = db.execute(
                "SELECT leg FROM slides WHERE mission=?", (mission,)
            ).fetchall()
            for row in rows:
                if row["leg"] not in legs:
                    db.execute(
                        "DELETE FROM slides WHERE mission=? AND leg=?",
                        (mission, row["leg"]),
                    )

    def missions(self):
        with self.connection() as db:
            return [r[0] for r in db.execute("SELECT DISTINCT mission FROM slides")]

    def recover(self):
        # Only the elected coordinator may recover abandoned running jobs.
        with self.connection() as db:
            db.execute("UPDATE slides SET state='queued' WHERE state='running'")

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM slides WHERE state='queued' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE slides SET state='running' WHERE token=?", (row["token"],)
                )
                return dict(row)
        return None

    def current(self, mission, leg, token):
        with self.connection() as db:
            row = db.execute(
                "SELECT token,state FROM slides WHERE mission=? AND leg=?",
                (mission, leg),
            ).fetchone()
            return bool(row and row["token"] == token and row["state"] != "dirty")

    def publish(self, mission, leg, token, snapshot, pdf, evidence, warning=None):
        with self.connection() as db:
            return (
                db.execute(
                    """UPDATE slides SET state=?, snapshot=?, pdf=?, evidence=?, warning=?
                WHERE mission=? AND leg=? AND token=? AND state='running'""",
                    (
                        "ready" if pdf and evidence else "failed",
                        snapshot,
                        pdf,
                        evidence,
                        warning,
                        mission,
                        leg,
                        token,
                    ),
                ).rowcount
                == 1
            )

    def records(self, mission):
        # Copy BLOBs in one SQLite read snapshot: exports own their bytes.
        with self.connection() as db:
            return {
                r["leg"]: dict(r)
                for r in db.execute("SELECT * FROM slides WHERE mission=?", (mission,))
            }


def default_store():
    from app.mission import storage

    return SlideStore(storage.MISSIONS_DIR / ".slide-cache" / "slides.sqlite3")
