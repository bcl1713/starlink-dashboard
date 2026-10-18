"""Public transport commands use existing receipts, epochs and version conflicts."""

from uuid import uuid4

from tests.operator.test_transport_contract import decision, row


def test_transport_api_roundtrip(api, record_data):
    epoch = api.get("/api/v2/operator/health").json()["api_epoch"]
    headers = {"Idempotency-Key": str(uuid4()), "X-Operator-Store-Epoch": epoch}
    data = decision(record_data, row(applied={"transport": "Ka"}))
    response = api.post("/api/v2/operator/records", json=data, headers=headers)
    assert response.status_code == 201, response.text
    assert (
        api.post("/api/v2/operator/records", json=data, headers=headers).json()
        == response.json()
    )
    saved = response.json()["saved_records"][0]
    path = "/api/v2/operator/records/" + saved["record_id"]
    headers["Idempotency-Key"] = str(uuid4())
    changed = data | {"expected_version": 1}
    changed["payload"] = data["payload"] | {"reason": "Preserve bandwidth"}
    assert api.put(path, json=changed, headers=headers).status_code == 200
    headers["Idempotency-Key"] = str(uuid4())
    assert api.put(path, json=changed, headers=headers).status_code == 409
    assert len(api.get(path + "/history").json()["items"]) == 2
