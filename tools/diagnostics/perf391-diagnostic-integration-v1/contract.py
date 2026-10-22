"""Offline closed sidecar validation, not an emitter or an integration analyzer."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

PACKAGE = Path(__file__).resolve().parent
CONTRACT = json.loads((PACKAGE / "contract.json").read_text())
VALIDATOR = Draft202012Validator(
    json.loads((PACKAGE / "integration-event-schema.json").read_text())
)


class ContractError(ValueError):
    pass


def capability(role, name):
    return (
        CONTRACT["capabilities"]
        .get(role, {})
        .get(name, CONTRACT["missing_capability"])
        .copy()
    )


def validate_event(event):
    errors = list(VALIDATOR.iter_errors(event))
    if errors:
        raise ContractError("; ".join(error.message for error in errors))
    if event["thread_cpu_ns"] is not None and (
        event["tid"] is None or event["thread_start_id"] is None
    ):
        raise ContractError(
            "CPU unavailable without native thread and thread start identity"
        )
    for name, value in event["identity"].items():
        if value is None and name not in event["unavailable"]:
            raise ContractError("null identity requires unavailable reason: " + name)
        if value is not None and name in event["unavailable"]:
            raise ContractError(
                "identity cannot be both available and unavailable: " + name
            )


class StreamValidator:
    """Incremental bounded state, shared by collection and offline validation."""

    def __init__(self, max_streams=4096):
        self.streams = {}
        self.clocks = {}
        self.max_streams = max_streams

    def accept(self, event):
        key = (event["run_id"], event["stream_id"])
        if key not in self.streams and len(self.streams) >= self.max_streams:
            raise ContractError("stream budget")
        _validate_events([event], self.streams, self.clocks)


def validate_stream(events):
    state = StreamValidator()
    for event in events:
        state.accept(event)


def _validate_events(events, streams, clocks):
    for event in events:
        validate_event(event)
        key = (event["run_id"], event["stream_id"])
        identity = tuple(
            event[k]
            for k in (
                "role",
                "emitter",
                "process_uuid",
                "pid",
                "process_start_id",
                "clock_id",
            )
        )
        document = (
            event["identity"].get("document_id")
            if event["emitter"] == "browser"
            else None
        )
        identity += (document, event["tid"], event["thread_start_id"])
        clock_key = (event["run_id"], event["clock_id"])
        # Backend streams are per native thread to preserve sequence order
        # without an emission mutex. time.monotonic_ns has one process clock;
        # sharing it across threads does not join different process origins.
        clock_owner = (
            tuple(event[k] for k in ("role", "process_uuid", "pid", "process_start_id"))
            if event["emitter"] != "browser"
            else (event["stream_id"], identity)
        )
        if clock_key in clocks and clocks[clock_key] != clock_owner:
            raise ContractError(
                "clock reused across process/document/stream identities"
            )
        clocks[clock_key] = clock_owner
        previous = streams.get(key)
        if previous:
            last_identity, seq, mono = previous
            if (
                identity != last_identity
                or event["seq"] != seq + 1
                or int(event["mono_ns"]) < mono
            ):
                raise ContractError(
                    "stream restart, sequence loss/reuse or clock discontinuity"
                )
        elif event["seq"] != 1:
            raise ContractError("missing beginning of stream")
        streams[key] = (identity, event["seq"], int(event["mono_ns"]))
