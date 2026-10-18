"""Manual service capability is independent from redundancy and telemetry."""

from copy import deepcopy

import pytest

from tests.operator.api_helpers import BASE, create, headers
from tests.operator.test_issue_api import issue_data, saved


def assessment(record_data, **fields):
    data = deepcopy(record_data)
    data["time"] = {}
    data["payload"] = {
        "entry_type": "capability_assessment",
        "title": "Synthetic secure voice",
        **fields,
    }
    return data


def test_functional_with_unavailable_backup(api, record_data):
    record = saved(
        create(
            api,
            assessment(
                record_data,
                functional_status="functional",
                redundancy_status="unavailable",
            ),
        )
    )
    assert record["payload"]["functional_status"] == "functional"
    assert record["payload"]["redundancy_status"] == "unavailable"
    assert record["provenance"]["kind"] == "operator_reported"


def test_one_dimension_does_not_freshen_other(api, record_data):
    data = assessment(
        record_data,
        functional_status="functional",
        functional_observed_at="2026-10-17T15:00:00Z",
        functional_time_precision="exact",
    )
    record = saved(create(api, data))
    data["payload"].update(
        redundancy_status="degraded",
        redundancy_observed_at="2026-10-17T16:00:00Z",
        redundancy_time_precision="approximate",
    )
    updated = saved(
        api.put(
            BASE + "/records/" + record["record_id"],
            json=dict(data, expected_version=1),
            headers=headers(api),
        ),
        200,
    )
    assert (
        updated["payload"]["functional_observed_at"]
        == record["payload"]["functional_observed_at"]
    )


def test_unknown_time_and_both_unknown(api, record_data):
    record = saved(create(api, assessment(record_data)))
    assert record["payload"]["functional_status"] == "unknown"
    assert record["payload"]["redundancy_status"] == "unknown"
    assert record["payload"]["functional_observed_at"] is None
    assert (
        saved(create(api, assessment(record_data)))["record_id"] != record["record_id"]
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"functional_observed_at": "2026-10-17T15:00:00Z"},
        {"functional_time_precision": "exact"},
        {
            "functional_time_precision": "exact",
            "functional_observed_at": "2026-10-17T16:02:00Z",
        },
        {"redundancy_status": "ready"},
    ],
)
def test_invalid_assessment_times(api, record_data, fields):
    assert create(api, assessment(record_data, **fields)).status_code == 422


def test_assessment_links_protect_subtype_and_removal(api, record_data):
    record = saved(create(api, assessment(record_data)))
    saved(create(api, issue_data(record_data, capability_id=record["record_id"])))
    assert (
        api.post(
            BASE + "/records/" + record["record_id"] + "/remove",
            json={"expected_version": 1},
            headers=headers(api),
        ).status_code
        == 409
    )
    data = deepcopy(record_data)
    assert (
        api.put(
            BASE + "/records/" + record["record_id"],
            json=dict(data, expected_version=1),
            headers=headers(api),
        ).status_code
        == 409
    )
