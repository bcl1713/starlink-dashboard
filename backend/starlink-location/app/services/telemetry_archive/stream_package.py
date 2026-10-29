"""Incremental deterministic CSV/ZIP publication with lossless compact columns."""

import csv
import hashlib
import io
import json
import zipfile
from uuid import uuid4

from app.mission.package.archive_errors import ArchiveCapacityError

from .compact import SeriesIndex

FULL_COLUMNS = [
    "timestamp_utc",
    "metric",
    "labels_json",
    "value",
    "availability",
    "source_observed_at_utc",
]
COMPACT_COLUMNS = [
    "timestamp_utc",
    "series_id",
    "value",
    "availability",
    "source_observed_at_utc",
]
EVENT_COLUMNS = [
    "event_id",
    "revision",
    "kind",
    "occurred_at_utc",
    "detected_at_utc",
    "source",
    "confidence",
    "evidence_json",
]
MAX_MEMBER_BYTES = 256 * 1024 * 1024


class MemberWriter:
    def __init__(self, archive, limit, check):
        self.archive, self.limit, self.check = archive, limit, check
        self.total, self.members = 0, {}

    def write(self, name, blocks):
        digest, size = hashlib.sha256(), 0
        entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        entry.compress_type, entry.external_attr = zipfile.ZIP_DEFLATED, 0o600 << 16
        with self.archive.open(entry, "w", force_zip64=True) as target:
            for block in blocks:
                self.check()
                self.total += len(block)
                if self.total > self.limit:
                    raise ArchiveCapacityError("supplementary-members", self.limit)
                target.write(block)
                digest.update(block)
                size += len(block)
        self.members[name] = {"sha256": digest.hexdigest(), "size": size}
        return digest.hexdigest()

    def document(self, name, value):
        return self.write(
            name,
            [json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True).encode()],
        )


def csv_blocks(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(
            [
                (
                    "'" + value
                    if isinstance(value, str)
                    and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                    else value
                )
                for value in row
            ]
        )
        if stream.tell() >= 65536:
            yield stream.getvalue().encode()
            stream.seek(0)
            stream.truncate()
    if stream.tell():
        yield stream.getvalue().encode()


def write_telemetry_package(
    output,
    mission_id,
    captures,
    *,
    representation="full",
    workdir,
    check,
    max_bytes=MAX_MEMBER_BYTES,
):
    if representation not in ("full", "compact"):
        raise ValueError("Unknown telemetry format")
    legs, count = [], 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        writer = MemberWriter(archive, max_bytes, check)
        for index, capture in enumerate(captures, 1):
            if capture.get("source_mode") != "live":
                raise ValueError(
                    "Cannot include simulation data in an operational package"
                )
            prefix, leg_count = f"legs/{index:03d}", [0]
            series = (
                capture.get("_index")
                or SeriesIndex(workdir / f"series-{uuid4().hex}.sqlite3", max_bytes)
                if representation == "compact"
                else None
            )
            try:

                def observations(capture=capture, series=series, leg_count=leg_count):
                    for sample in capture["samples"]:
                        check()
                        leg_count[0] += 1
                        availability = (
                            "missing"
                            if sample["value"] is None
                            else (
                                "source_freshness_unknown"
                                if sample["labels"].get("source")
                                == "cached_last_known_proxy"
                                else "observed"
                            )
                        )
                        identity = (
                            [series.identify(sample)]
                            if series
                            else [
                                sample["metric"],
                                json.dumps(sample["labels"], sort_keys=True),
                            ]
                        )
                        yield [
                            sample["timestamp"],
                            *identity,
                            sample["value"],
                            availability,
                            sample.get("observed_at"),
                        ]

                checksums = {
                    "observations.csv": writer.write(
                        f"{prefix}/observations.csv",
                        csv_blocks(
                            COMPACT_COLUMNS if series else FULL_COLUMNS, observations()
                        ),
                    )
                }
                if series:
                    checksums["series.csv"] = writer.write(
                        f"{prefix}/series.csv",
                        csv_blocks(
                            ["series_id", "metric", "labels_json"], series.rows()
                        ),
                    )
                event_rows = (
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
                )
                checksums["events.csv"] = writer.write(
                    f"{prefix}/events.csv", csv_blocks(EVENT_COLUMNS, event_rows)
                )
                metadata = {
                    k: v for k, v in capture.items() if k not in ("samples", "_index")
                }
                metadata.update(
                    checksum=checksums,
                    observation_count=leg_count[0],
                    telemetry_format=representation,
                )
                writer.document(f"{prefix}/manifest.json", metadata)
                legs.append(
                    {
                        k: metadata.get(k)
                        for k in (
                            "mission_id",
                            "leg_id",
                            "revision",
                            "start",
                            "end",
                            "state",
                            "source_mode",
                            "complete",
                            "observation_count",
                        )
                    }
                    | {"path": prefix, "checksum": checksums}
                )
                count += leg_count[0]
            finally:
                if series and series is not capture.get("_index"):
                    series.close()
        partial = any(
            not leg.get("complete") or leg.get("state") != "sealed" for leg in legs
        )
        writer.document(
            "manifest.json",
            {
                "schema_version": 1 if representation == "full" else 2,
                "artifact_kind": "telemetry",
                "mission_id": mission_id,
                "partial": partial,
                "source_mode": "live",
                "telemetry_format": representation,
                "legs": legs,
            },
        )
        writer.document(
            "dataset.json",
            {
                "telemetry_format": representation,
                "observation_columns": (
                    COMPACT_COLUMNS if representation == "compact" else FULL_COLUMNS
                ),
                "time_basis": "UTC; source_observed_at_utc is independent and may be unknown",
                "missing_value": "empty value with availability=missing; measured zero is 0",
                "compact_join": "Join each leg observations.series_id to that leg series.series_id. No observations are downsampled.",
                "source_semantics": "cached_last_known_proxy describes cached egress/geolocation proxy evidence with unknown freshness; it does not verify routing or a handover",
            },
        )
        writer.write(
            "README.txt",
            [
                b"Mission telemetry dataset\nAll retained live observations are preserved, including nulls and source labels.\nRead dataset.json and each leg manifest for schemas, source identity, gaps and completeness.\nCompact format: join observations.csv to series.csv on series_id within each leg.\nThe mission archive also contains planning snapshots and the complete operations journal.\nPlanning at export time is not necessarily the original preflight forecast.\nNo pattern detection or after-action conclusions are generated.\n"
            ],
        )
    check()
    return {
        "members": writer.members,
        "uncompressed_bytes": writer.total,
        "observation_count": count,
        "legs": legs,
        "telemetry_format": representation,
    }
