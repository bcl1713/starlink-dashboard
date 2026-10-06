"""Publication is atomic, settings-bound, durable and response-lease safe."""

import pytest
from app.models.aviation_grid import GfsSelection
from app.services.aviation_weather.settings import AviationSettingsStore

from tests.fixtures.gfs_fields import RUN
from tests.unit.test_gfs_grid import candidate


def store(root):
    from app.services.aviation_weather.gfs.store import GfsProductStore

    settings = AviationSettingsStore(root / "settings.json")
    enabled = settings.update({"winds": True, "temperature": True})
    return (
        GfsProductStore(
            root / "artifacts", root / "mailbox", settings, clock=lambda: RUN / 1000
        ),
        settings,
        enabled,
    )


def test_two_envelopes_share_immutable_buffers_and_original_age(tmp_path):
    products, _settings, enabled = store(tmp_path)
    products.publish(candidate(tmp_path / "work"), enabled.revision)
    current = products.read_current(GfsSelection(), RUN + 3600000)
    assert len(current) == 2
    assert current[0].product_id != current[1].product_id
    assert current[0].instance_id != current[1].instance_id
    assert (
        products.root / "products" / current[0].instance_id / "u.bin"
    ).stat().st_ino == (
        products.root / "products" / current[1].instance_id / "u.bin"
    ).stat().st_ino
    assert products.read_current(GfsSelection(), RUN + 18 * 3600000) == ()
    assert products.read_current(GfsSelection(pressure_pa=30000), RUN) == ()


def test_obsolete_revision_and_bad_candidate_cannot_replace_pointer(tmp_path):
    products, settings, enabled = store(tmp_path)
    products.publish(candidate(tmp_path / "first"), enabled.revision)
    original = (products.root / "current.json").read_bytes()
    changed = settings.update({"winds": False, "temperature": False})
    with pytest.raises(ValueError):
        products.publish(candidate(tmp_path / "second"), enabled.revision)
    assert (products.root / "current.json").read_bytes() == original
    new = candidate(tmp_path / "third")
    (new.directory / "u.bin").write_bytes(b"bad")
    with pytest.raises(ValueError):
        products.publish(new, changed.revision)
    assert (products.root / "current.json").read_bytes() == original


def test_pointer_failure_preserves_previous_and_lease_prevents_retention(
    tmp_path, monkeypatch
):
    products, _settings, enabled = store(tmp_path)
    products.publish(candidate(tmp_path / "first"), enabled.revision)
    current = products.read_current(GfsSelection(), RUN)
    original = (products.root / "current.json").read_bytes()
    import app.services.aviation_weather.gfs.store as module

    original_atomic = module.atomic_json

    def fail_pointer(path, value):
        if path.name == "current.json":
            raise OSError("injected fsync/pointer failure")
        return original_atomic(path, value)

    monkeypatch.setattr(module, "atomic_json", fail_pointer)
    with pytest.raises(OSError):
        products.publish(
            candidate(tmp_path / "second", surface=99999), enabled.revision
        )
    assert (products.root / "current.json").read_bytes() == original
    with products.lease(current[0].instance_id):
        products.prune(RUN + 18 * 3600000)
        assert (products.root / "products" / current[0].instance_id).exists()
    products.prune(RUN + 18 * 3600000)
    assert not (products.root / "products" / current[0].instance_id).exists()


def test_disk_reserve_failure_preserves_current(tmp_path, monkeypatch):
    products, _settings, enabled = store(tmp_path)
    products.publish(candidate(tmp_path / "first"), enabled.revision)
    original = (products.root / "current.json").read_bytes()
    from collections import namedtuple

    import app.services.aviation_weather.gfs.store as module

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        module.shutil, "disk_usage", lambda path: Usage(4 * 1024**3, 4 * 1024**3, 0)
    )
    with pytest.raises(ValueError):
        products.publish(
            candidate(tmp_path / "second", surface=99999), enabled.revision
        )
    assert (products.root / "current.json").read_bytes() == original


def test_expired_candidate_and_changed_horizon_cannot_publish(tmp_path):
    from app.services.aviation_weather.gfs.store import GfsProductStore

    products, settings, enabled = store(tmp_path)
    expired = GfsProductStore(
        products.root,
        products.mailbox,
        settings,
        clock=lambda: (RUN + 18 * 3600000) / 1000,
    )
    with pytest.raises(ValueError):
        expired.publish(candidate(tmp_path / "expired"), enabled.revision)
    changed = settings.update(
        {"gfs_selection": {"pressure_pa": 50000, "horizon_hours": 12}}
    )
    with pytest.raises(ValueError):
        products.publish(candidate(tmp_path / "changed"), changed.revision)


def test_actual_inventory_midpoint_limits_retained_validity(tmp_path):
    from dataclasses import replace

    from app.services.aviation_weather.gfs.decode import decode_bundle
    from app.services.aviation_weather.gfs.grid import normalize_grid

    products, settings, _enabled = store(tmp_path)
    from tests.fixtures.gfs_fields import grib_bundle

    bundle = replace(
        grib_bundle(tmp_path / "source"), available_leads=(0, 10800, 21600, 32400)
    )
    result = normalize_grid(
        decode_bundle(bundle),
        GfsSelection(horizon_hours=6),
        tmp_path / "candidate",
        clock=lambda: RUN / 1000,
    )
    selected = settings.update(
        {"gfs_selection": {"pressure_pa": 50000, "horizon_hours": 6}}
    )
    products.publish(result, selected.revision)
    assert products.read_current(selected.gfs_selection, RUN)
    # A target halfway between F006 and F009 still selects F006; one millisecond
    # later cannot keep displaying the obsolete instant as a current selection.
    assert products.read_current(selected.gfs_selection, RUN + 5400000)
    assert products.read_current(selected.gfs_selection, RUN + 5400001) == ()


def test_third_run_is_refused_while_an_old_reader_holds_a_lease(tmp_path):
    from app.services.aviation_weather.gfs.decode import decode_bundle
    from app.services.aviation_weather.gfs.grid import normalize_grid

    from tests.fixtures.gfs_fields import grib_bundle

    products, _settings, enabled = store(tmp_path)
    products.publish(candidate(tmp_path / "first"), enabled.revision)
    first = products.read_current(GfsSelection(), RUN)[0]
    with products.lease(first.instance_id):
        for hours in (6, 12):
            run = RUN + hours * 3600000
            products.clock = lambda run=run: run / 1000
            bundle = grib_bundle(tmp_path / str(hours) / "source", run_at_ms=run)
            new = normalize_grid(
                decode_bundle(bundle),
                GfsSelection(),
                tmp_path / str(hours) / "grid",
                clock=lambda run=run: run / 1000,
            )
            products.prune(run)
            if hours == 6:
                products.publish(new, enabled.revision)
            else:
                with pytest.raises(ValueError):
                    products.publish(new, enabled.revision)
