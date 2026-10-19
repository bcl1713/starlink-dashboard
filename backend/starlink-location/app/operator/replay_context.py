"""Read-time replay relevance, independent of immutable journal association."""


def current_records(records, health):
    if not health.mission_journal:
        return records
    return [
        r
        for r in records
        if evidence_current(r, health)
        or (
            not r.deleted
            and (
                (
                    r.payload.entry_type == "call"
                    and r.time.occurred_at is None
                    and r.payload.status in ("tentative", "scheduled", "delayed")
                )
                or (r.payload.entry_type == "issue" and r.payload.status != "resolved")
            )
        )
    ]


def source_run(health):
    return health.replay_run_id if health.mission_journal else health.simulation_run_id


def operating_run(health):
    if not health.mission_journal:
        return health.simulation_run_id
    return (
        health.operating_context_id
        or health.replay_run_id
        or "idle:" + health.simulation_run_id
    )


def evidence_current(record, health):
    if not health.mission_journal:
        return True
    if health.operating_context_id is not None:
        return record.provenance.operating_context_id == health.operating_context_id
    return (
        health.replay_run_id is not None
        and record.provenance.replay_run_id == health.replay_run_id
    )
