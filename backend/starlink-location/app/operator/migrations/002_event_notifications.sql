CREATE TABLE event_occurrences (
    occurrence_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    anchor_utc TEXT,
    created_at TEXT NOT NULL,
    event_json TEXT NOT NULL CHECK (json_valid(event_json))
);
CREATE TABLE event_heads (
    event_id TEXT PRIMARY KEY,
    occurrence_id TEXT NOT NULL REFERENCES event_occurrences(occurrence_id),
    retired INTEGER NOT NULL DEFAULT 0 CHECK (retired IN (0, 1))
);
CREATE TABLE event_transitions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    occurrence_id TEXT NOT NULL REFERENCES event_occurrences(occurrence_id),
    state TEXT NOT NULL CHECK (state IN ('accepted', 'retired')),
    recorded_at TEXT NOT NULL,
    UNIQUE (occurrence_id, state)
);
CREATE TABLE event_acknowledgments (
    acknowledgment_id TEXT PRIMARY KEY,
    occurrence_id TEXT NOT NULL REFERENCES event_occurrences(occurrence_id),
    severity_generation INTEGER NOT NULL CHECK (severity_generation BETWEEN 0 AND 3),
    command_id TEXT NOT NULL REFERENCES commands(command_id) DEFERRABLE INITIALLY DEFERRED,
    acknowledged_at TEXT NOT NULL,
    UNIQUE (occurrence_id, severity_generation)
);
CREATE INDEX event_occurrences_mission ON event_occurrences(mission_id, created_at);
CREATE TRIGGER event_occurrences_no_update BEFORE UPDATE ON event_occurrences
BEGIN SELECT RAISE(ABORT, 'immutable event occurrence'); END;
CREATE TRIGGER event_occurrences_no_delete BEFORE DELETE ON event_occurrences
BEGIN SELECT RAISE(ABORT, 'immutable event occurrence'); END;
CREATE TRIGGER event_transitions_no_update BEFORE UPDATE ON event_transitions
BEGIN SELECT RAISE(ABORT, 'immutable event transition'); END;
CREATE TRIGGER event_transitions_no_delete BEFORE DELETE ON event_transitions
BEGIN SELECT RAISE(ABORT, 'immutable event transition'); END;
CREATE TRIGGER event_acknowledgments_no_update BEFORE UPDATE ON event_acknowledgments
BEGIN SELECT RAISE(ABORT, 'immutable event acknowledgment'); END;
CREATE TRIGGER event_acknowledgments_no_delete BEFORE DELETE ON event_acknowledgments
BEGIN SELECT RAISE(ABORT, 'immutable event acknowledgment'); END;

CREATE TABLE event_tiers (
    occurrence_id TEXT NOT NULL REFERENCES event_occurrences(occurrence_id),
    severity_generation INTEGER NOT NULL CHECK (severity_generation BETWEEN 0 AND 3),
    accepted_at TEXT NOT NULL,
    PRIMARY KEY (occurrence_id, severity_generation)
);
CREATE TRIGGER event_tiers_no_update BEFORE UPDATE ON event_tiers
BEGIN SELECT RAISE(ABORT, 'immutable event tier'); END;
CREATE TRIGGER event_tiers_no_delete BEFORE DELETE ON event_tiers
BEGIN SELECT RAISE(ABORT, 'immutable event tier'); END;
