"""Optional API labels remain unverified attribution, never backend identity."""

from copy import deepcopy
from uuid import uuid4

import pytest
from tests.operator.api_helpers import BASE, create, headers
from tests.operator.test_call_api import call_data


@pytest.mark.parametrize("kind", ["journal_entry", "call"])
def test_label_replay_and_replacement_preserve_immutable_backend_attribution(
    api, record_data, kind
):
    data = (
        call_data(record_data, prep_lead_minutes=0)
        if kind == "call"
        else deepcopy(record_data)
    )
    data["operator_label"] = "Fictional self-reported label A"
    key = str(uuid4())
    first = create(api, data, key)
    assert first.status_code == 201, first.text
    receipt = first.json()
    row = receipt["saved_records"][0]
    assert row["author"]["operator_label"] == data["operator_label"]
    assert row["author"]["backend"] != data["operator_label"]
    replay = create(api, data, key)
    assert replay.status_code == first.status_code
    assert replay.json() == receipt

    data["operator_label"] = "Fictional self-reported label B"
    path = BASE + "/records/" + row["record_id"]
    replacement = api.put(
        path, json=dict(data, expected_version=1), headers=headers(api)
    )
    assert replacement.status_code == 200, replacement.text
    current = replacement.json()["saved_records"][0]
    assert current["author"]["backend"] == row["author"]["backend"]
    history = api.get(path + "/history").json()
    assert [
        item["record"]["author"]["operator_label"] for item in history["items"]
    ] == [
        "Fictional self-reported label A",
        "Fictional self-reported label B",
    ]
    assert history["items"][0]["record"] == row
    assert history["items"][1]["record"] == current
    assert (
        create(api, dict(data, author={"backend": "forged identity"})).status_code
        == 422
    )
    assert create(api, dict(data, operator_label="x" * 201)).status_code == 422
