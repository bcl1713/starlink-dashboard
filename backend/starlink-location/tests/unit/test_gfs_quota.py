"""Scientific attempts/bytes remain bounded across process restarts."""

import pytest


def test_attempt_budget_survives_restart_and_clock_rollback(tmp_path):
    from app.services.aviation_weather.gfs.quota import GfsQuota

    now = [100000.0]
    with GfsQuota(tmp_path, clock=lambda: now[0]) as first:
        for _ in range(20):
            first.attempt()
    with GfsQuota(tmp_path, clock=lambda: now[0]) as second:
        with pytest.raises(ValueError):
            second.attempt()
        now[0] += 60
        second.attempt()
        now[0] -= 100
        with pytest.raises(ValueError):
            second.attempt()


def test_byte_budget_reserves_before_transfer_and_charges_failures(tmp_path):
    from app.services.aviation_weather.gfs.quota import GfsQuota

    with GfsQuota(tmp_path, clock=lambda: 100000.0) as first:
        for _ in range(160):
            token = first.reserve(32 * 1024**2)
            first.charge(token, 32 * 1024**2)
            first.release(token)
    with GfsQuota(tmp_path, clock=lambda: 100000.0) as restarted, pytest.raises(
        ValueError
    ):
        restarted.reserve(1)


def test_only_two_exchanges_hold_reservations(tmp_path):
    from app.services.aviation_weather.gfs.quota import GfsQuota

    with GfsQuota(tmp_path, clock=lambda: 100000.0) as quota:
        first, second = quota.reserve(32), quota.reserve(32)
        with pytest.raises(ValueError):
            quota.reserve(1)
        quota.release(first)
        third = quota.reserve(1)
        quota.release(second)
        quota.release(third)


def test_dead_reservation_is_conservatively_charged(tmp_path):
    import json

    from app.services.aviation_weather.gfs.quota import GfsQuota

    token = "a" * 32
    (tmp_path / token).touch()
    (tmp_path / "budget.json").write_text(
        json.dumps(
            {
                "last": 100000,
                "day": 1,
                "bytes": 5 * 1024**3 - 32,
                "attempts": [],
                "tokens": {token: 32},
            }
        )
    )
    with GfsQuota(tmp_path, clock=lambda: 100000.0) as recovered, pytest.raises(
        ValueError
    ):
        recovered.reserve(1)


def test_transfer_crossing_utc_day_charges_received_day(tmp_path):
    import json

    from app.services.aviation_weather.gfs.quota import GfsQuota

    now = [86399.0]
    with GfsQuota(tmp_path, clock=lambda: now[0]) as quota:
        token = quota.reserve(32)
        now[0] = 86401.0
        quota.charge(token, 16)
        quota.release(token)
        quota.attempt()
    data = json.loads((tmp_path / "budget.json").read_text())
    assert data["day"] == 1
    assert data["bytes"] == 16
