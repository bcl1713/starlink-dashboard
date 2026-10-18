"""Snapshot follow-up state with no delivery or timer assertions."""

import pytest

from tests.operator.api_helpers import BASE, create
from tests.operator.test_issue_api import issue_data, replace, saved


@pytest.mark.parametrize(
    "due,state",
    [
        ("15:59:59", "overdue"),
        ("16:00:00", "due"),
        ("16:00:01", "upcoming"),
        (None, "unscheduled"),
    ],
)
def test_followup_utc_boundaries(api, record_data, due, state):
    record = saved(
        create(
            api,
            issue_data(record_data, follow_up_at=f"2026-10-17T{due}Z" if due else None),
        )
    )
    view = api.get(BASE + "/records/" + record["record_id"]).json()
    assert view["follow_up"]["state"] == state
    page = api.get(
        BASE + "/records", params={"mission_id": "demo-mission", "record_type": "issue"}
    ).json()
    assert page["items"][0]["follow_up"]["state"] == state


def test_resolve_clear_reopen_no_resurrection(api, record_data):
    data = issue_data(record_data, follow_up_at="2026-10-17T15:00:00Z")
    record = saved(create(api, data))
    resolved = saved(
        replace(api, data, record, status="resolved", follow_up_at=None), 200
    )
    assert (
        api.get(BASE + "/records/" + record["record_id"]).json()["follow_up"]["state"]
        == "inactive"
    )
    reopened = saved(
        replace(api, data, resolved, status="reopened", follow_up_at=None), 200
    )
    assert reopened["payload"]["follow_up_at"] is None
    assert (
        api.get(BASE + "/records/" + record["record_id"]).json()["follow_up"]["state"]
        == "unscheduled"
    )


def test_regressed_clock_is_unknown(api, record_data, clock):
    record = saved(
        create(api, issue_data(record_data, follow_up_at="2026-10-17T17:00:00Z"))
    )
    clock.advance(-60)
    assert (
        api.get(BASE + "/records/" + record["record_id"]).json()["follow_up"]["state"]
        == "unknown"
    )
