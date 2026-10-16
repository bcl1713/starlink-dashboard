"""Position-driven synthetic egress, isolated from production IP discovery."""

from app.services.ground_entry_point import GroundEntryPoint
from app.services.pop.geometry import nearest_pop
from app.services.pop.models import PopCatalog, PopObservation


def unknown_simulation_observation() -> PopObservation:
    return PopObservation(ip=None, entry=None, status="unknown", source="simulation")


class SimulationPopResolver:
    """Give sorted stable catalog identities documentation-only IPv4 addresses."""

    def __init__(self, catalog: PopCatalog):
        self.catalog = catalog
        self._previous_id = None
        self._entries = {
            site.id: GroundEntryPoint(
                ip=f"192.0.2.{index}",
                city=site.city,
                country=site.country,
                latitude=site.latitude,
                longitude=site.longitude,
            )
            for index, site in enumerate(sorted(catalog.sites, key=lambda s: s.id), 1)
        }

    def update(self, latitude: float, longitude: float) -> PopObservation:
        if not self._entries:
            return unknown_simulation_observation()
        try:
            winner = nearest_pop(latitude, longitude, self.catalog, self._previous_id)
            if winner is None:
                # At initialization choose the first *tied* ID, even when the
                # catalog's lowest ID is elsewhere. No boundary hysteresis.
                for site_id in self._entries:
                    winner = nearest_pop(latitude, longitude, self.catalog, site_id)
                    if winner is not None:
                        break
        except (ValueError, TypeError):
            self.reset()
            return unknown_simulation_observation()
        self._previous_id = winner
        entry = self._entries[winner]
        return PopObservation(
            ip=entry.ip, entry=entry, status="known", source="simulation"
        )

    def reset(self) -> None:
        self._previous_id = None


class SimulationPopObservationProvider:
    """Mode-aware local observation provider with independent simulation state."""

    def __init__(self, lifecycle_provider=lambda: None):
        self.lifecycle_provider = lifecycle_provider
        self._identity = None
        self._resolver = None

    def __call__(self, mode, telemetry, catalog):
        if mode == "live":
            from app.services.ground_entry_point import get_cached_pop_observation

            self._identity, self._resolver = None, None
            return get_cached_pop_observation()
        return self.simulation_observation(
            telemetry, catalog, lifecycle_token=self.lifecycle_provider()
        )

    def simulation_observation(self, telemetry, catalog, *, lifecycle_token):
        """Allow a candidate replay frame to carry its not-yet-committed run ID."""
        if catalog is None:
            self._identity, self._resolver = None, None
            return unknown_simulation_observation()
        identity = (catalog.fingerprint, lifecycle_token)
        if identity != self._identity:
            self._identity = identity
            self._resolver = SimulationPopResolver(catalog)
        return self._resolver.update(
            telemetry.position.latitude, telemetry.position.longitude
        )
