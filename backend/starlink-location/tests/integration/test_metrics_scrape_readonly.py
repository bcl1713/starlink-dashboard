"""Scraping must not acquire synthetic telemetry or advance producer state."""

from app.simulation.coordinator import SimulationCoordinator


def test_one_hundred_http_scrapes_construct_no_simulators(test_client, monkeypatch):
    """A scrape must not create a new synthetic source alongside the running one."""
    constructions = []
    original_init = SimulationCoordinator.__init__

    def record_construction(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        constructions.append(self)

    monkeypatch.setattr(SimulationCoordinator, "__init__", record_construction)
    for _ in range(100):
        response = test_client.get("/metrics")
        assert response.status_code == 200
        assert response.text.endswith("# EOF\n")

    assert len(constructions) == 0, "scrapes acquired synthetic telemetry"
