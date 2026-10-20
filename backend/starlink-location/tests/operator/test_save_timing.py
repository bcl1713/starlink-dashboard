"""Small real SQLite/API measurements; no synthetic infrastructure or SLAs."""

from statistics import median
from time import perf_counter

from tests.operator.api_helpers import BASE, create
from tests.operator.test_conference_api import conference_data


def test_local_save_measurements(api, record_data):
    samples = []
    for index in range(5):
        data = conference_data(record_data, status="preparing")
        data["payload"]["title"] = f"Timing {index}"
        started = perf_counter()
        response = create(api, data)
        acknowledged = perf_counter()
        assert response.status_code == 201, response.text
        saved = response.json()["saved_records"][0]
        current = api.get(BASE + "/records/" + saved["record_id"])
        read = perf_counter()
        assert current.status_code == 200
        assert current.json()["record"]["record_id"] == saved["record_id"]
        samples.append(((acknowledged - started) * 1000, (read - started) * 1000))
    print(
        {
            "samples": len(samples),
            "api_post_median_ms": round(median(x[0] for x in samples), 2),
            "api_post_and_current_read_median_ms": round(
                median(x[1] for x in samples), 2
            ),
        }
    )


def test_save_exposes_separate_request_admission_and_command_timings(api, record_data):
    response = create(api, conference_data(record_data, status="preparing"))
    assert response.status_code == 201
    values = dict(
        part.strip().split(";dur=")
        for part in response.headers["Server-Timing"].split(",")
    )
    assert {
        "operator_gate",
        "operator_request",
        "operator_binding",
        "operator_command",
    } <= values.keys()
    assert all(float(value) >= 0 for value in values.values())
    assert float(values["operator_request"]) >= float(values["operator_command"])
