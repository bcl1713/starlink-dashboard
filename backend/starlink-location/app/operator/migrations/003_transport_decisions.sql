-- Backed-up exclusive maintenance connection disables FK enforcement before BEGIN.
CREATE TEMP TABLE transport_sequence AS
SELECT seq FROM sqlite_sequence WHERE name='revisions';
DROP VIEW current_records;
DROP TRIGGER records_advance;
CREATE TABLE revisions_new (
    journal_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    previous_version INTEGER,
    command_id TEXT NOT NULL REFERENCES commands(command_id) DEFERRABLE INITIALLY DEFERRED,
    operation TEXT NOT NULL CHECK (operation IN ('create', 'update', 'remove', 'restore')),
    reason TEXT,
    reason_origin TEXT CHECK (reason_origin IN ('automatic', 'operator')),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    record_type TEXT NOT NULL CHECK (record_type IN
        ('journal_entry', 'call', 'conference', 'participation', 'issue', 'risk', 'transport_report', 'transport_decision')),
    mission_id TEXT NOT NULL,
    leg_id TEXT,
    scope TEXT NOT NULL CHECK (scope IN ('mission', 'preflight', 'leg', 'between_legs', 'postflight')),
    deleted INTEGER NOT NULL CHECK (deleted IN (0, 1)),
    recorded_at TEXT NOT NULL,
    author_json TEXT NOT NULL CHECK (json_valid(author_json)),
    time_json TEXT NOT NULL CHECK (json_valid(time_json)),
    provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    UNIQUE (record_id, version),
    FOREIGN KEY (record_id, previous_version) REFERENCES revisions(record_id, version),
    CHECK ((scope = 'leg' AND leg_id IS NOT NULL) OR (scope <> 'leg' AND leg_id IS NULL)),
    CHECK (deleted = (operation = 'remove')),
    CHECK ((reason IS NULL AND reason_origin IS NULL AND operation = 'create') OR
           (reason IS NOT NULL AND reason_origin IS NOT NULL AND
            length(trim(reason)) > 0 AND length(reason) <= 1000)),
    CHECK ((operation = 'create' AND version = 1 AND previous_version IS NULL) OR
           (operation <> 'create' AND version > 1 AND previous_version IS NOT NULL
            AND previous_version = version - 1))
);
INSERT INTO revisions_new SELECT * FROM revisions;
DROP TABLE revisions;
ALTER TABLE revisions_new RENAME TO revisions;
UPDATE sqlite_sequence SET seq = max(seq, coalesce((SELECT max(seq) FROM transport_sequence), 0)) WHERE name='revisions';
DROP TABLE transport_sequence;
CREATE VIEW current_records AS
SELECT v.* FROM records r JOIN revisions v
ON v.record_id = r.record_id AND v.version = r.current_version;
CREATE INDEX revisions_mission_seq ON revisions(mission_id, journal_seq);
CREATE INDEX revisions_command ON revisions(command_id);
CREATE TRIGGER revisions_no_update BEFORE UPDATE ON revisions
BEGIN SELECT RAISE(ABORT, 'immutable revision'); END;
CREATE TRIGGER revisions_no_delete BEFORE DELETE ON revisions
BEGIN SELECT RAISE(ABORT, 'immutable revision'); END;
CREATE TRIGGER revisions_predecessor BEFORE INSERT ON revisions
WHEN NEW.operation <> 'create' AND NOT EXISTS (
    SELECT 1 FROM records WHERE record_id = NEW.record_id AND current_version = NEW.previous_version
)
BEGIN SELECT RAISE(ABORT, 'invalid predecessor'); END;
CREATE TRIGGER records_advance BEFORE UPDATE ON records
WHEN NEW.record_id <> OLD.record_id OR NEW.current_version <> OLD.current_version + 1
OR NOT EXISTS (SELECT 1 FROM revisions WHERE record_id = NEW.record_id
               AND version = NEW.current_version AND previous_version = OLD.current_version)
BEGIN SELECT RAISE(ABORT, 'pointer must advance one revision'); END;
