"""Add frozen local journal and #349 telemetry bytes to the portable mission ZIP."""

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from app.operator.projections import capture_projection
from app.operator.runtime import enabled, runtime_for

from .archive_attachment import append_archive

__all__ = ["append_archive", "capture_archive", "journal_files"]

MAX_ARCHIVE_INPUT_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_FILES_BYTES = 256 * 1024 * 1024


def canonical(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def journal_files(bundle):
    """Keep acceptance-order audit intact; provide a separate actual-time index."""
    files = dict(bundle.files)
    current = json.loads(files["operations/current.json"])
    revisions = [
        json.loads(line) for line in files["operations/audit.jsonl"].splitlines()
    ]
    activity = [
        json.loads(line) for line in files["operations/activity.jsonl"].splitlines()
    ]
    chronology = {}
    for item in activity:
        issue = item.get("issue_update")
        chronology[item["journal_seq"]] = {
            **item,
            "effective_at": (
                issue["effective_at"]
                if issue is not None
                else item["time"].get("occurred_at")
            ),
            "time_basis": (
                "issue_update.effective_at" if issue is not None else "time.occurred_at"
            ),
        }

    def chronological_key(record):
        effective = chronology[record["journal_seq"]]["effective_at"]
        return effective is None, effective or "", record["journal_seq"]

    chronological = sorted(revisions, key=chronological_key)
    files["operations/journal.json"] = canonical(
        {
            "schema_version": 1,
            "mission_id": bundle.manifest.mission_id,
            "store_id": str(bundle.store_id),
            "high_water": bundle.high_water,
            "source_mode": bundle.source_mode,
            "simulation_run_id": bundle.simulation_run_id,
            "replay_run_id": bundle.manifest.replay_run_id,
            "mission_journal": bundle.manifest.mission_journal,
            "import_policy": "archive_only; ordinary_plan_import_does_not_restore_operator_records",
            "ordering": {
                "activity_and_audit": "acceptance_sequence",
                "chronological_revisions": "issue_update.effective_at_when_present; otherwise_actual_occurred_at_utc; all_original_revisions_retained",
                "unknown_actual_time": "after_known_actual_times; acceptance_sequence_tiebreaker",
                "planned_times": "retained_separately; never_substituted_for_actual_time",
            },
            "current_records": current,
            "chronological_revisions": chronological,
            "chronological_activity": [
                chronology[r["journal_seq"]] for r in chronological
            ],
        }
    )
    summary = [
        f"Mission handover: {bundle.manifest.mission_id}",
        f"Journal sequence: {bundle.high_water}; source: {bundle.source_mode}",
        "Snapshot summary; operator reports and modeled predictions do not verify actual routing.",
    ]
    for record in current:
        payload = record["payload"]
        historical = bundle.manifest.mission_journal and (
            bundle.manifest.replay_run_id is None
            or record["provenance"].get("replay_run_id")
            != bundle.manifest.replay_run_id
        )
        summary.append(
            ("Historical replay report; not current readiness | " if historical else "")
            + f"{record['record_type']}: {payload['title']} | {payload.get('status', payload.get('state', 'recorded'))} | scope={record['scope']} leg={record['leg_id'] or 'mission'}"
        )
    files["operations/handover.txt"] = ("\n".join(summary) + "\n").encode("utf-8")
    manifest = bundle.manifest.model_dump(mode="json")
    manifest["checksums"] = {
        name: hashlib.sha256(body).hexdigest() for name, body in files.items()
    }
    manifest["projections"].update(
        {
            "operations/journal.json": "versioned_chronological_journal",
            "operations/handover.txt": "current_snapshot_handover",
        }
    )
    files["operations/manifest.json"] = canonical(manifest)
    return files


def capture_archive(request, mission_id, *, owner=None, telemetry_format="full"):
    """Capture locally, without querying Prometheus or optional model providers.

    Each store pins its own revision. Capture intervals explicitly do not claim a
    simultaneous transaction across planning, Operator and per-leg archive stores.
    """
    components, files, attachments = {}, {}, []
    with runtime_for(request) as runtime:
        if runtime is not None and enabled(runtime):
            if runtime.service is None or not runtime.health().ready:
                raise RuntimeError("Operator archive is unavailable")
            started = runtime.clock.now().isoformat()
            bundle = capture_projection(
                runtime.service.store,
                mission_id=mission_id,
                include_audit=True,
                include_events=True,
                max_input_bytes=MAX_ARCHIVE_INPUT_BYTES,
            )
            files.update(journal_files(bundle))
            components["operator"] = {
                "status": "included",
                "store_id": str(bundle.store_id),
                "api_epoch": str(bundle.api_epoch),
                "high_water": bundle.high_water,
                "source_mode": bundle.source_mode,
                "simulation_run_id": bundle.simulation_run_id,
                "replay_run_id": bundle.manifest.replay_run_id,
                "mission_journal": bundle.manifest.mission_journal,
                "capture_started_at": started,
                "capture_finished_at": runtime.clock.now().isoformat(),
                "revision_recorded_at": (
                    bundle.manifest.component_capture_times["operator"].isoformat()
                    if bundle.manifest.component_capture_times["operator"]
                    else None
                ),
            }
        else:
            components["operator"] = {"status": "disabled"}
    flight = getattr(request.app.state, "flight_event_runtime", None)
    if flight is None:
        components["telemetry"] = {
            "status": "unavailable",
            "reason": "archive_runtime_unavailable",
        }
    elif owner is not None:
        from app.services.telemetry_archive.stream_package import (
            write_telemetry_package,
        )
        from app.services.telemetry_archive.stream_reader import stream_captures

        mission = flight.preparations.load_mission(mission_id)
        if mission is None:
            raise KeyError("Mission not found")
        if not mission.legs:
            components["telemetry"] = {
                "status": "not_applicable",
                "reason": "no_executable_legs",
            }
        else:
            started = datetime.now(timezone.utc).isoformat()
            journal_bytes = sum(len(body) for body in files.values())
            with stream_captures(
                flight.archive,
                mission_id,
                [leg.id for leg in mission.legs],
                check=owner.check,
                workdir=owner.directory,
            ) as captures, owner.open_sidecar() as output:
                metadata = write_telemetry_package(
                    output,
                    mission_id,
                    captures,
                    representation=telemetry_format,
                    workdir=owner.directory,
                    check=owner.check,
                    max_bytes=MAX_ARCHIVE_FILES_BYTES - journal_bytes,
                )
            attachments.append(owner.publish(metadata))
            components["telemetry"] = {
                "status": "included",
                "capture_started_at": started,
                "capture_finished_at": datetime.now(timezone.utc).isoformat(),
                "telemetry_format": telemetry_format,
                "observation_count": metadata["observation_count"],
                "legs": [
                    {
                        k: c.get(k)
                        for k in (
                            "mission_id",
                            "leg_id",
                            "revision",
                            "state",
                            "complete",
                            "source_mode",
                        )
                    }
                    for c in metadata["legs"]
                ],
            }
    else:
        started = datetime.now(timezone.utc).isoformat()
        data = flight.preparations.capture_snapshot(
            mission_id,
            allow_partial=True,
            allow_empty=True,
            max_input_bytes=MAX_ARCHIVE_INPUT_BYTES,
        )
        if not data["captures"]:
            components["telemetry"] = {
                "status": "not_applicable",
                "reason": "no_executable_legs",
            }
        else:
            from app.services.telemetry_archive.package import build_telemetry_package

            payload = build_telemetry_package(
                mission_id, data["captures"], allow_partial=True
            )
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                files.update(
                    {
                        "telemetry/" + name: archive.read(name)
                        for name in archive.namelist()
                    }
                )
            components["telemetry"] = {
                "status": "included",
                "capture_started_at": started,
                "capture_finished_at": datetime.now(timezone.utc).isoformat(),
                "legs": [
                    {
                        k: c.get(k)
                        for k in (
                            "mission_id",
                            "leg_id",
                            "revision",
                            "state",
                            "complete",
                            "source_mode",
                        )
                    }
                    for c in data["captures"]
                ],
            }
    if sum(len(body) for body in files.values()) > MAX_ARCHIVE_FILES_BYTES:
        raise RuntimeError("Mission archive file size limit exceeded")
    result = {
        "schema_version": 1,
        "capture_policy": "sequential_component_snapshots",
        "components": components,
        "files": {name: body.decode("utf-8") for name, body in files.items()},
    }
    if attachments:
        result["attachments"] = attachments
    return result
