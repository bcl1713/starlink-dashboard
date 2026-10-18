"""Add frozen local journal and #349 telemetry bytes to the portable mission ZIP."""

import copy
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from app.mission.exporter.export_cancel import check_cancelled
from app.operator.projections import capture_projection
from app.operator.runtime import enabled, runtime_for

from .streams import iter_zip_blocks, new_package_stream


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
        summary.append(
            f"{record['record_type']}: {payload['title']} | {payload.get('status', payload.get('state', 'recorded'))} | scope={record['scope']} leg={record['leg_id'] or 'mission'}"
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


def capture_archive(request, mission_id):
    """Capture locally, without querying Prometheus or optional model providers.

    Each store pins its own revision. Capture intervals explicitly do not claim a
    simultaneous transaction across planning, Operator and per-leg archive stores.
    """
    components, files = {}, {}
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
            )
            files.update(journal_files(bundle))
            components["operator"] = {
                "status": "included",
                "store_id": str(bundle.store_id),
                "api_epoch": str(bundle.api_epoch),
                "high_water": bundle.high_water,
                "source_mode": bundle.source_mode,
                "simulation_run_id": bundle.simulation_run_id,
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
    else:
        started = datetime.now(timezone.utc).isoformat()
        data = flight.preparations.capture_snapshot(
            mission_id, allow_partial=True, allow_empty=True
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
    return {
        "schema_version": 1,
        "capture_policy": "sequential_component_snapshots",
        "components": components,
        "files": {name: body.decode("utf-8") for name, body in files.items()},
    }


def append_archive(stream, snapshot, *, planning_fingerprint, cancel):
    """Copy existing members byte-for-byte; publish exactly one outer manifest."""
    result = new_package_stream()
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream) as source, zipfile.ZipFile(
            result, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            manifest = json.loads(source.read("manifest.json"))
            files = snapshot["files"]
            if set(files) & set(source.namelist()):
                raise ValueError("Archive component path collision")
            for entry in source.infolist():
                check_cancelled(cancel)
                if entry.filename == "manifest.json":
                    continue
                with source.open(entry) as incoming, target.open(
                    copy.copy(entry), "w"
                ) as outgoing:
                    for block in iter_zip_blocks(incoming):
                        check_cancelled(cancel)
                        outgoing.write(block)
            for name, text in files.items():
                check_cancelled(cancel)
                target.writestr(name, text.encode("utf-8"))
            manifest["archive_components"] = {
                "schema_version": 1,
                "capture_policy": snapshot["capture_policy"],
                "planning_fingerprint": planning_fingerprint,
                "components": snapshot["components"],
                "checksums": {
                    name: hashlib.sha256(text.encode("utf-8")).hexdigest()
                    for name, text in files.items()
                },
                "import_policy": "planning_only; archival_components_do_not_restore_active_stores",
            }
            manifest["file_structure"]["archive_files"] = sorted(files)
            manifest["statistics"]["total_files"] = len(target.namelist()) + 1
            target.writestr("manifest.json", canonical(manifest))
        check_cancelled(cancel)
        result.seek(0)
        return result
    except BaseException:
        result.close()
        raise
