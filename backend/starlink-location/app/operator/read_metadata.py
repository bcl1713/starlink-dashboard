"""Read-time metadata is never inserted into immutable revisions or receipts."""

from .issue_followup import derive_issue_followup
from .time_models import utc_timestamp


def freshness(record, *, as_of, policies):
    provenance = record.provenance
    reference = provenance.source_ref
    threshold = policies.get(reference.producer_id) if reference else None
    source_time = (
        provenance.observed_at
        if provenance.kind == "observed"
        else provenance.predicted_at if provenance.kind == "modeled" else None
    )
    status = "unknown"
    if source_time is not None and threshold is not None:
        age = (as_of - source_time).total_seconds()
        if age >= 0:
            status = "stale" if age >= threshold else "fresh"
    else:
        threshold = None
    if status == "unknown":
        threshold = None
    return {
        "status": status,
        "threshold_seconds": threshold,
        "as_of": utc_timestamp(as_of)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
    }


def read_record(record, runtime, *, as_of=None):
    captured_at = as_of or runtime.clock.now()
    result = {
        "schema_version": 1,
        "record": record.model_dump(mode="json"),
        "association": runtime.service.references.resolve(record),
        "freshness": freshness(
            record,
            as_of=as_of or runtime.clock.now(),
            policies=runtime.freshness_policies,
        ),
    }
    health = runtime.health()
    result["operational_current"] = not health.mission_journal or (
        health.replay_run_id is not None
        and record.provenance.replay_run_id == health.replay_run_id
    )
    if record.record_type == "issue":
        result["follow_up"] = derive_issue_followup(
            record,
            as_of=captured_at,
            clock_regression=runtime.health().clock_regression,
        )
    return result


def read_page(page, runtime):
    result = page.model_dump(mode="json")
    result["items"] = [
        read_record(record, runtime, as_of=page.as_of) for record in page.items
    ]
    return result
