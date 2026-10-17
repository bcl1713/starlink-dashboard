"""Synthetic egress follows emitted geography, without external discovery."""

import pytest

from app.services.pop.catalog import DEFAULT_CATALOG_PATH, load_catalog
from app.services.pop.models import PopCatalog, PopSite
from app.simulation.pop import SimulationPopObservationProvider, SimulationPopResolver


def catalog(*sites):
    return PopCatalog(
        sites=tuple(
            PopSite(
                id=id,
                city=id.upper(),
                country="US",
                latitude=lat,
                longitude=lon,
                source="fixture",
                coordinate_source="fixture",
            )
            for id, lat, lon in sites
        ),
        fingerprint="fixture",
    )


@pytest.fixture(autouse=True)
def forbid_discovery(monkeypatch):
    import app.services.ground_entry_point as gep

    def forbidden(*args, **kwargs):
        raise AssertionError("Simulation attempted external discovery")

    monkeypatch.setattr(gep, "resolve_public_ip", forbidden)
    monkeypatch.setattr(gep, "geolocate_public_ip", forbidden)
    monkeypatch.setattr(gep, "resolve_public_ip_via_dns", forbidden)
    monkeypatch.setattr(gep, "resolve_public_ip_via_cloudflare_trace", forbidden)
    monkeypatch.setattr(gep._resolver, "_geolocator", forbidden)


def test_position_changes_ip_and_city_only_when_region_changes():
    resolver = SimulationPopResolver(catalog(("a", 0, -10), ("b", 0, 10)))
    a = resolver.update(0, -8)
    assert (a.ip, a.entry.city, a.source, a.status) == (
        "192.0.2.1",
        "A",
        "simulation",
        "known",
    )
    assert resolver.update(0, -1) == a
    b = resolver.update(0, 1)
    assert (b.ip, b.entry.city, b.entry.latitude, b.entry.longitude) == (
        "192.0.2.2",
        "B",
        0,
        10,
    )


def test_seed_addresses_are_stable_across_catalog_ordering():
    original = load_catalog(DEFAULT_CATALOG_PATH)
    reverse = original.model_copy(update={"sites": tuple(reversed(original.sites))})
    first, second = SimulationPopResolver(original), SimulationPopResolver(reverse)
    for index, site in enumerate(sorted(original.sites, key=lambda s: s.id), 1):
        assert first.update(site.latitude, site.longitude).ip == f"192.0.2.{index}"
        assert second.update(site.latitude, site.longitude) == first.update(
            site.latitude, site.longitude
        )


def test_tie_retains_previous_winner_and_reset_uses_sorted_identity():
    resolver = SimulationPopResolver(catalog(("b", 0, 10), ("a", 0, -10)))
    assert resolver.update(0, 1).entry.city == "B"
    assert resolver.update(0, 0).entry.city == "B"
    assert resolver.update(0, -0.00001).entry.city == "A"
    resolver.update(0, 1)
    resolver.reset()
    assert resolver.update(0, 0).entry.city == "A"


def test_dateline_movement_uses_great_circle_nearest_region():
    resolver = SimulationPopResolver(catalog(("a", 0, 170), ("b", 0, -170)))
    assert resolver.update(0, 179).entry.city == "A"
    assert resolver.update(0, 180).entry.city == "A"
    assert resolver.update(0, -179).entry.city == "B"


@pytest.mark.parametrize(
    "lat,lon", [(float("nan"), 0), (0, float("inf")), (91, 0), (0, 181)]
)
def test_invalid_position_clears_current_evidence(lat, lon):
    resolver = SimulationPopResolver(catalog(("a", 0, -10), ("b", 0, 10)))
    resolver.update(0, 1)
    unknown = resolver.update(lat, lon)
    assert (unknown.ip, unknown.entry, unknown.status, unknown.source) == (
        None,
        None,
        "unknown",
        "simulation",
    )
    assert resolver.update(0, 0).entry.city == "A"


def test_provider_isolates_live_cache_and_resets_on_mode_seek_and_missing_catalog(
    monkeypatch,
):
    from app.services import ground_entry_point as gep
    from app.services.pop.models import PopObservation
    from tests.conftest import default_mock_telemetry

    observed = PopObservation(
        ip="203.0.113.9",
        entry=gep.GroundEntryPoint("203.0.113.9", "Live", "US", 1, 2),
        status="known",
        source="live",
    )
    monkeypatch.setattr(gep, "get_cached_pop_observation", lambda: observed)
    epoch = [0]
    provider = SimulationPopObservationProvider(lambda: epoch[0])
    sample = default_mock_telemetry()
    sample.position.latitude, sample.position.longitude = 0, 1
    sites = catalog(("a", 0, -10), ("b", 0, 10))
    assert provider("simulation", sample, sites).entry.city == "B"
    sample.position.longitude = 0
    assert provider("simulation", sample, sites).entry.city == "B"
    epoch[0] += 1  # Both forward and backward seeks are lifecycle changes.
    assert provider("simulation", sample, sites).entry.city == "A"
    sample.position.longitude = 1
    provider("simulation", sample, sites)
    assert provider("simulation", sample, None).status == "unknown"
    sample.position.longitude = 0
    assert provider("simulation", sample, sites).entry.city == "A"
    sample.position.longitude = 1
    provider("simulation", sample, sites)
    assert provider("live", sample, sites) == observed
    sample.position.longitude = 0
    assert provider("simulation", sample, sites).entry.city == "A"
    assert gep.get_cached_pop_observation() == observed


@pytest.mark.parametrize("operation", ["reset", "seek", "config"])
def test_coordinator_reset_and_seek_reset_provider_tie(operation, coordinator):
    from tests.conftest import default_mock_telemetry

    provider = SimulationPopObservationProvider(lambda: coordinator.pop_lifecycle_token)
    sample = default_mock_telemetry()
    sample.position.latitude, sample.position.longitude = 0, 1
    sites = catalog(("a", 0, -10), ("b", 0, 10))
    assert provider("simulation", sample, sites).entry.city == "B"
    if operation == "seek":
        coordinator.set_position_progress(0.8)
    elif operation == "config":
        coordinator.update_config(coordinator.config)
    else:
        coordinator.reset()
    sample.position.longitude = 0
    assert provider("simulation", sample, sites).entry.city == "A"


@pytest.mark.parametrize(
    "start,end,want",
    [
        ((60, -60), (60, 60), (73.897886248, 0)),
        ((0, 170), (0, -170), (0, 180)),
    ],
)
def test_route_following_emits_great_circle_midpoint(start, end, want):
    from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
    from app.simulation.kml_follower import KMLRouteFollower

    route = ParsedRoute(
        metadata=RouteMetadata(name="arc", file_path="arc.kml", point_count=2),
        points=[
            RoutePoint(latitude=lat, longitude=lon, sequence=i)
            for i, (lat, lon) in enumerate((start, end))
        ],
    )
    position = KMLRouteFollower(route, deviation_degrees=0).get_position(0.5)
    assert position["latitude"] == pytest.approx(want[0], abs=1e-8)
    assert abs(position["longitude"]) == pytest.approx(abs(want[1]), abs=1e-8)
