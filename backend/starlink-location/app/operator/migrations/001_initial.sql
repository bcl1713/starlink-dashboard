CREATE TABLE store_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    store_id TEXT NOT NULL UNIQUE,
    source_mode TEXT NOT NULL CHECK (source_mode IN ('live', 'simulation')),
    simulation_run_id TEXT,
    created_at TEXT NOT NULL,
    CHECK ((source_mode = 'live' AND simulation_run_id IS NULL) OR
           (source_mode = 'simulation' AND length(simulation_run_id) > 0))
);
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE commands (
    command_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    request_hash TEXT NOT NULL,
    contract_version INTEGER NOT NULL CHECK (contract_version = 1),
    recorded_at TEXT NOT NULL,
    response_status INTEGER NOT NULL CHECK (response_status BETWEEN 200 AND 299),
    response_json TEXT NOT NULL CHECK (json_valid(response_json))
);
CREATE TABLE revisions (
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
        ('journal_entry', 'call', 'conference', 'participation', 'issue', 'risk', 'transport_report')),
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
CREATE TABLE records (
    record_id TEXT PRIMARY KEY,
    current_version INTEGER NOT NULL,
    FOREIGN KEY (record_id, current_version) REFERENCES revisions(record_id, version)
);
CREATE VIEW current_records AS
SELECT v.* FROM records r JOIN revisions v
ON v.record_id = r.record_id AND v.version = r.current_version;
CREATE TABLE current_links (
    from_id TEXT NOT NULL REFERENCES records(record_id),
    relation TEXT NOT NULL,
    to_id TEXT NOT NULL REFERENCES records(record_id),
    PRIMARY KEY (from_id, relation, to_id),
    CHECK (from_id <> to_id)
);
CREATE INDEX revisions_mission_seq ON revisions(mission_id, journal_seq);
CREATE INDEX revisions_command ON revisions(command_id);
CREATE INDEX links_target ON current_links(to_id);
CREATE TRIGGER revisions_no_update BEFORE UPDATE ON revisions
BEGIN SELECT RAISE(ABORT, 'immutable revision'); END;
CREATE TRIGGER revisions_no_delete BEFORE DELETE ON revisions
BEGIN SELECT RAISE(ABORT, 'immutable revision'); END;
CREATE TRIGGER commands_no_update BEFORE UPDATE ON commands
BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
CREATE TRIGGER commands_no_delete BEFORE DELETE ON commands
BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
CREATE TRIGGER revisions_predecessor BEFORE INSERT ON revisions
WHEN NEW.operation <> 'create' AND NOT EXISTS (
    SELECT 1 FROM records WHERE record_id = NEW.record_id AND current_version = NEW.previous_version
)
BEGIN SELECT RAISE(ABORT, 'invalid predecessor'); END;
CREATE TRIGGER records_initial BEFORE INSERT ON records
WHEN NEW.current_version <> 1
BEGIN SELECT RAISE(ABORT, 'initial pointer must be one'); END;
CREATE TRIGGER records_advance BEFORE UPDATE ON records
WHEN NEW.record_id <> OLD.record_id OR NEW.current_version <> OLD.current_version + 1
OR NOT EXISTS (SELECT 1 FROM revisions WHERE record_id = NEW.record_id
               AND version = NEW.current_version AND previous_version = OLD.current_version)
BEGIN SELECT RAISE(ABORT, 'pointer must advance one revision'); END;
CREATE TRIGGER records_no_delete BEFORE DELETE ON records
BEGIN SELECT RAISE(ABORT, 'record deletion forbidden'); END;
