"""Deterministic mission ZIPs pin immutable observed capture revisions."""

import csv
import hashlib
import io
import json
import zipfile


def _csv(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(
            [
                (
                    (
                        "'" + value
                        if value.startswith(("=", "+", "-", "@", "\t", "\r"))
                        else value
                    )
                    if isinstance(value, str)
                    else value
                )
                for value in row
            ]
        )
    return stream.getvalue().encode("utf-8")


def build_telemetry_package(
    mission_id: str, captures: list[dict], *, allow_partial: bool
) -> bytes:
    if not captures:
        raise ValueError("Mission telemetry is incomplete or unavailable")
    if any(capture.get("source_mode") != "live" for capture in captures):
        raise ValueError("Cannot include simulation data in an operational package")
    partial = any(
        not capture.get("complete") or capture.get("state") != "sealed"
        for capture in captures
    )
    if partial and not allow_partial:
        raise ValueError(
            "Mission telemetry is incomplete; request a labeled partial package"
        )
    files = []
    manifests = []
    for index, capture in enumerate(captures, 1):
        prefix = f"legs/{index:03d}"
        samples = capture.get("samples", [])
        observations = _csv(
            [
                "timestamp_utc",
                "metric",
                "labels_json",
                "value",
                "availability",
                "source_observed_at_utc",
            ],
            [
                [
                    sample["timestamp"],
                    sample["metric"],
                    json.dumps(sample["labels"], sort_keys=True),
                    sample["value"],
                    (
                        "missing"
                        if sample["value"] is None
                        else (
                            "source_freshness_unknown"
                            if sample["labels"].get("source")
                            == "cached_last_known_proxy"
                            else "observed"
                        )
                    ),
                    sample.get("observed_at"),
                ]
                for sample in samples
            ],
        )
        events = _csv(
            [
                "event_id",
                "revision",
                "kind",
                "occurred_at_utc",
                "detected_at_utc",
                "source",
                "confidence",
                "evidence_json",
            ],
            [
                [
                    event["event_id"],
                    event["revision"],
                    event["kind"],
                    event["occurred_at"],
                    event["detected_at"],
                    event["source"],
                    event["confidence"],
                    json.dumps(event["evidence"], sort_keys=True),
                ]
                for event in capture.get("events", [])
            ],
        )
        manifest = {
            key: value for key, value in capture.items() if key not in ("samples",)
        }
        manifest["checksum"] = {
            "observations.csv": hashlib.sha256(observations).hexdigest(),
            "events.csv": hashlib.sha256(events).hexdigest(),
        }
        files.extend(
            [
                (f"{prefix}/observations.csv", observations),
                (f"{prefix}/events.csv", events),
                (
                    f"{prefix}/manifest.json",
                    json.dumps(manifest, sort_keys=True, indent=2).encode(),
                ),
            ]
        )
        manifests.append(
            {
                "leg_id": capture["leg_id"],
                "revision": capture["revision"],
                "path": prefix,
                "start": capture["start"],
                "end": capture["end"],
                "checksum": manifest["checksum"],
                "complete": capture.get("complete", False),
            }
        )
    manifest = {
        "schema_version": 1,
        "artifact_kind": "telemetry",
        "mission_id": mission_id,
        "partial": partial,
        "source_mode": "live",
        "legs": manifests,
    }
    files.insert(
        0, ("manifest.json", json.dumps(manifest, sort_keys=True, indent=2).encode())
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files:
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, content)
    return output.getvalue()
