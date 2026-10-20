"""HTTP fixture helpers for the public Operator API tests."""

from uuid import uuid4

BASE = "/api/v2/operator"


def headers(api, key=None):
    return {
        "Idempotency-Key": key or str(uuid4()),
        "X-Operator-Store-Epoch": api.get(BASE + "/health").json()["api_epoch"],
    }


def create(api, data, key=None):
    return api.post(BASE + "/records", json=data, headers=headers(api, key))
