import asyncio

import pytest
from app.models.overview_adsb import AdsbContact
from app.services.adsb_lol import AdsbProviderError, AdsbProviderResult
from app.services.overview_adsb_settings import AdsbSettingsStore
from app.services.overview_adsb_traffic import AdsbTrafficService


class Clock:
    now = 1791028800.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class Provider:
    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.military = []
        self.hexes = {}
        self.errors = {}
        self.block = None
        self.entered = asyncio.Event()
        self.active = 0
        self.max_active = 0

    async def fetch(self, key, contacts):
        self.calls.append(key)
        self.active += 1
        self.max_active = max(self.active, self.max_active)
        try:
            self.entered.set()
            if self.block:
                await self.block.wait()
            if key in self.errors:
                raise self.errors[key]
            return AdsbProviderResult(list(contacts), self.clock() * 1000)
        finally:
            self.active -= 1

    async def fetch_military(self):
        return await self.fetch("military", self.military)

    async def fetch_hexes(self, hex_codes):
        contacts = [c for hex_code in hex_codes for c in self.hexes.get(hex_code, [])]
        return await self.fetch("hex:" + ",".join(hex_codes), contacts)


def contact(clock, hex="00AB12", **changes):
    return AdsbContact(
        hex=hex,
        latitude=40,
        longitude=-75,
        military=True,
        position_observed_at_ms=clock() * 1000,
        acquired_at_ms=clock() * 1000,
        **changes,
    )


@pytest.fixture
def runtime(tmp_path):
    clock = Clock()
    store = AdsbSettingsStore(tmp_path / "adsb.json")
    provider = Provider(clock)
    service = AdsbTrafficService(store, provider, clock, clock)
    return store, provider, service, clock


async def test_viewers_share_one_cycle(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    provider.military = [contact(clock)]
    provider.block = asyncio.Event()
    requests = [asyncio.create_task(service.refresh_once()) for _ in range(5)]
    await provider.entered.wait()
    for _ in range(20):
        assert service.read().contacts == []
    provider.block.set()
    await asyncio.gather(*requests)
    assert provider.calls == ["military"]
    assert provider.max_active == 1
    assert service.read().contacts[0].hex == "00AB12"


async def test_disabled_never_acquires(runtime):
    store, provider, service, _ = runtime
    await service.refresh_once()
    assert provider.calls == []
    store.update({"enabled": True})
    store.update({"enabled": False})
    service.settings_changed()
    await service.refresh_once()
    assert provider.calls == []


async def test_mode_controls_acquisition(runtime):
    store, provider, service, clock = runtime
    store.update(
        {
            "enabled": True,
            "include_hexes": ["00AB12", "000002", "000003"],
            "exclude_hexes": ["000003"],
        }
    )
    provider.military = [contact(clock)]
    await service.refresh_once()
    assert provider.calls == ["military", "hex:000002"]
    store.update({"mode": "included_only"})
    service.settings_changed()
    clock.advance(15)
    await service.refresh_once()
    assert provider.calls[-1] == "hex:00AB12,000002"
    store.update({"include_hexes": []})
    service.settings_changed()
    clock.advance(15)
    before = list(provider.calls)
    await service.refresh_once()
    assert provider.calls == before


async def test_missing_position_does_not_renew_cached_contact(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    original = contact(clock)
    provider.military = [original]
    await service.refresh_once()
    provider.military = []
    clock.advance(30)
    await service.refresh_once()
    assert (
        service.read().contacts[0].position_observed_at_ms
        == original.position_observed_at_ms
    )
    clock.advance(90)
    assert service.read().contacts == []


async def test_older_duplicate_cannot_overwrite_cache(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    original = contact(clock, callsign="NEW")
    provider.military = [original]
    await service.refresh_once()
    clock.advance(15)
    provider.military = [
        original.model_copy(
            update={
                "position_observed_at_ms": original.position_observed_at_ms - 1000,
                "callsign": "OLD",
                "acquired_at_ms": clock() * 1000,
            }
        )
    ]
    await service.refresh_once()
    assert service.read().contacts[0].callsign == "NEW"


async def test_fresh_returning_inclusion_reappears(runtime):
    store, provider, service, clock = runtime
    store.update(
        {"enabled": True, "mode": "included_only", "include_hexes": ["00AB12"]}
    )
    provider.hexes["00AB12"] = [contact(clock)]
    await service.refresh_once()
    clock.advance(120)
    assert service.read().contacts == []
    assert store.get().include_hexes == ["00AB12"]
    provider.hexes["00AB12"] = [contact(clock)]
    await service.refresh_once()
    assert len(service.read().contacts) == 1


async def test_source_failures_are_independent(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True, "include_hexes": ["000002"]})
    provider.errors["military"] = AdsbProviderError("Provider HTTP 503")
    provider.hexes["000002"] = [contact(clock, "000002")]
    await service.refresh_once()
    bundle = service.read()
    assert [c.hex for c in bundle.contacts] == ["000002"]
    sources = {s.key: s for s in bundle.sources}
    assert sources["military"].error
    assert sources["hex:000002"].last_success_at_ms == clock() * 1000
    provider.errors = {"hex:000002": AdsbProviderError("Provider HTTP 503")}
    clock.advance(15)
    provider.military = [contact(clock)]
    await service.refresh_once()
    sources = {s.key: s for s in service.read().sources}
    assert sources["military"].error is None
    assert sources["hex:000002"].error


async def test_backoff_and_retry_after(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    provider.errors["military"] = AdsbProviderError("Provider HTTP 503")
    for delay in [15, 30, 60, 120, 240, 300]:
        await service.refresh_once()
        status = service.read().sources[0]
        assert status.retry_at_ms == (clock() + delay) * 1000
        before = len(provider.calls)
        clock.advance(delay - 0.001)
        await service.refresh_once()
        assert len(provider.calls) == before
        clock.advance(0.001)
    provider.errors = {}
    await service.refresh_once()
    assert service.read().sources[0].retry_at_ms is None
    clock.advance(15)
    provider.errors["military"] = AdsbProviderError("Provider HTTP 429", 600)
    await service.refresh_once()
    assert service.read().sources[0].retry_at_ms == (clock() + 600) * 1000


@pytest.mark.parametrize(
    "initial,pause,resume,key",
    [
        ({"enabled": True}, {"enabled": False}, {"enabled": True}, "military"),
        (
            {"enabled": True},
            {"mode": "included_only"},
            {"mode": "military_and_included"},
            "military",
        ),
        (
            {"enabled": True, "mode": "included_only", "include_hexes": ["00AB12"]},
            {"exclude_hexes": ["00AB12"]},
            {"exclude_hexes": []},
            "hex:00AB12",
        ),
        (
            {"enabled": True, "mode": "included_only", "include_hexes": ["00AB12"]},
            {"include_hexes": []},
            {"include_hexes": ["00AB12"]},
            "hex:00AB12",
        ),
    ],
)
async def test_settings_round_trip_preserves_retry_deadline(
    runtime, initial, pause, resume, key
):
    store, provider, service, clock = runtime
    store.update(initial)
    provider.errors[key] = AdsbProviderError("Provider HTTP 429", 600)
    started = clock()
    await service.refresh_once()
    store.update(pause)
    service.settings_changed()
    assert service.read().sources == []
    clock.advance(15)
    store.update(resume)
    service.settings_changed()
    await service.refresh_once()
    assert provider.calls == [key]
    assert service.read().sources[0].retry_at_ms == (started + 600) * 1000
    clock.advance(584.999)
    await service.refresh_once()
    assert provider.calls == [key]
    clock.advance(0.001)
    provider.errors.clear()
    await service.refresh_once()
    assert provider.calls == [key, key]
    assert service.read().sources[0].retry_at_ms is None


@pytest.mark.parametrize(
    "changes",
    [{"exclude_hexes": ["00AB12"]}, {"mode": "included_only"}, {"enabled": False}],
)
async def test_save_race_discards_obsolete_cycle(runtime, changes):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    provider.military = [contact(clock)]
    provider.block = asyncio.Event()
    refresh = asyncio.create_task(service.refresh_once())
    await provider.entered.wait()
    store.update(changes)
    service.settings_changed()
    if changes == {"enabled": False}:
        store.update({"enabled": True})
        service.settings_changed()
    provider.block.set()
    await refresh
    assert service.read().settings_revision == store.get().revision
    assert service.read().contacts == []


async def test_shutdown_cancels_tasks_and_clears_ephemeral_cache(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    provider.military = [contact(clock)]
    provider.block = asyncio.Event()
    await service.start()
    await provider.entered.wait()
    await service.aclose()
    assert provider.active == 0
    assert service.read().contacts == []
    assert store.get().enabled is True


async def test_hex_acquisition_is_one_shared_batch(runtime):
    store, provider, service, _ = runtime
    hexes = [f"{i:06X}" for i in range(10)]
    store.update({"enabled": True, "mode": "included_only", "include_hexes": hexes})
    provider.block = asyncio.Event()
    refresh = asyncio.create_task(service.refresh_once())
    await provider.entered.wait()
    await asyncio.sleep(0)
    assert provider.max_active == 1
    provider.block.set()
    await refresh
    assert provider.calls == ["hex:" + ",".join(hexes)]


async def test_settings_failure_stops_acquisition_until_recovered(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    provider.military = [contact(clock)]
    await service.refresh_once()
    old = store._path.read_bytes()
    store._path.write_text("{corrupt")
    with pytest.raises(ValueError):
        service.read()
    clock.advance(15)
    await service.refresh_once()
    assert provider.calls == ["military"]
    store._path.write_bytes(old)
    await service.refresh_once()
    assert len(provider.calls) == 2


async def test_cycles_never_catch_up_after_long_acquisition(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    provider.block = asyncio.Event()
    refresh = asyncio.create_task(service.refresh_once())
    await provider.entered.wait()
    clock.advance(20)
    provider.block.set()
    await refresh
    await service.refresh_once()
    assert provider.calls == ["military"]
    clock.advance(15)
    await service.refresh_once()
    assert provider.calls == ["military", "military"]


async def test_independent_store_writer_is_applied_on_read(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True})
    provider.military = [contact(clock)]
    await service.refresh_once()
    AdsbSettingsStore(store._path).update({"exclude_hexes": ["00AB12"]})
    assert service.read().contacts == []
    assert service.read().settings_revision == 2


async def test_catalog_independent_selection_and_shared_acquisition(runtime):
    store, provider, service, clock = runtime
    store.update(
        {
            "enabled": True,
            "mode": "included_only",
            "include_hexes": ["000002"],
            "exclude_hexes": ["000002", "00AB12"],
            "callsign_substrings": ["MATCH"],
        }
    )
    provider.military = [contact(clock, callsign="OTHER")]
    provider.hexes["000002"] = [
        contact(clock, "000002").model_copy(update={"military": False})
    ]
    assert service.read_catalog().contacts == []
    await asyncio.gather(*(service.refresh_once() for _ in range(5)))
    assert provider.calls == ["military", "hex:000002"]
    assert service.read().contacts == []
    assert [c.hex for c in service.read_catalog().contacts] == ["000002", "00AB12"]
    store.update({"callsign_substrings": [], "exclude_hexes": []})
    service.settings_changed()
    assert [c.hex for c in service.read().contacts] == ["000002"]
    assert len(service.read_catalog().contacts) == 2


async def test_catalog_demand_expires_without_extending_contact_lifetime(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True, "mode": "included_only"})
    provider.military = [contact(clock)]
    service.read_catalog()
    await service.refresh_once()
    clock.advance(15)
    await service.refresh_once()
    clock.advance(15)
    await service.refresh_once()
    assert provider.calls == ["military", "military"]
    clock.advance(90)
    assert service.read_catalog().contacts == []
    await service.refresh_once()
    assert provider.calls == ["military", "military", "military"]
    assert service.read_catalog().contacts == []


async def test_disabled_catalog_never_acquires(runtime):
    store, provider, service, _ = runtime
    assert service.read_catalog().contacts == []
    await service.refresh_once()
    assert provider.calls == []
    store.update({"enabled": True, "mode": "included_only"})
    await service.refresh_once()
    assert provider.calls == []


async def test_catalog_lease_round_trip_keeps_rate_limit(runtime):
    store, provider, service, clock = runtime
    store.update({"enabled": True, "mode": "included_only"})
    provider.errors["military"] = AdsbProviderError("Provider HTTP 429", 600)
    service.read_catalog()
    await service.refresh_once()
    clock.advance(31)
    await service.refresh_once()
    assert service.read().sources == []
    assert service.read_catalog().sources[0].retry_at_ms == (clock() + 569) * 1000
    await service.refresh_once()
    assert provider.calls == ["military"]
