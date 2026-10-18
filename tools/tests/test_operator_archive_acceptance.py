"""Validate the full synthetic fixture against real schemas before Docker builds."""

from contextlib import nullcontext
from types import SimpleNamespace

from test_operator_journal_acceptance import implementation


def test_archive_fixture_runs_real_flights_and_typed_journal(tmp_path, monkeypatch):
    implementation()
    import archive_fixture
    from seed import seed_demo
    from scenario import ScenarioClock
    from app.mission import storage
    from app.operator.runtime import OperatorRuntime
    from app.operator.settings import OperatorSettings
    from app.operator.models import RecordFilter
    from app.services.route_manager import RouteManager
    from app.services.poi_manager import POIManager
    from scenario import pop_inputs

    class Clock(ScenarioClock):
        def set(self, now):
            self.current = now

    clock = Clock()
    seed = seed_demo(tmp_path, clock=clock, mode="simulation")
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    runtime = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=tmp_path / "operator",
            source_mode="simulation",
            simulation_run_id=seed["run_id"],
        ),
        clock=clock,
    )
    routes = RouteManager(tmp_path / "routes")
    route = pop_inputs(clock)["route"].model_copy(
        update={"route_id": "synthetic-route"}
    )
    routes.add_route(route.route_id, route)
    state = SimpleNamespace(
        operator_binding=SimpleNamespace(access=lambda: nullcontext(runtime)),
        route_manager=routes,
        poi_manager=POIManager(tmp_path / "pois.json"),
    )
    main = SimpleNamespace(app=SimpleNamespace(state=state))
    # This check validates fixture inputs; production rendering is independently
    # exercised by the Docker browser acceptance, not a host child process here.
    monkeypatch.setattr(archive_fixture, "start_runtime", lambda *args: None)
    try:
        archive_fixture.initialize(main, tmp_path)
        records = runtime.service.list(
            RecordFilter(mission_id=archive_fixture.MISSION)
        ).items
        assert {"preflight", "leg", "between_legs", "postflight"} <= {
            r.scope for r in records
        }
        assert any(r.record_type == "transport_decision" for r in records)
        assert any(r.version == 2 and r.payload.entry_type == "issue" for r in records)
        for leg in storage.load_mission_v2(archive_fixture.MISSION).legs:
            capture = state.flight_event_runtime.archive.capture(
                archive_fixture.MISSION, leg.id
            )
            assert capture["state"] == "sealed"
            assert {"takeoff", "landed", "on_blocks"} <= {
                r["kind"] for r in capture["events"]
            }
    finally:
        if getattr(state, "flight_event_runtime", None):
            state.flight_event_runtime.close()
        runtime.close()
