from datetime import datetime, timedelta, timezone

import pytest

from app.services.orbital_viewers import OrbitalViewers


def test_leases_renew_expire_release_and_bound_capacity():
    now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    viewers = OrbitalViewers()
    for i in range(128):
        assert viewers.acquire(str(i), now) == now + timedelta(seconds=75)
    with pytest.raises(OverflowError):
        viewers.acquire("extra", now)
    assert viewers.acquire("0", now + timedelta(seconds=30)) == now + timedelta(
        seconds=105
    )
    assert viewers.count(now + timedelta(seconds=75)) == 1
    viewers.release("0")
    viewers.release("0")
    assert viewers.count(now) == 0
