"""Starlink Location Backend - FastAPI Application."""

import asyncio
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import (
    active_x_link,
    aviation_weather,
    config,
    export,
    flight_status,
    geojson,
    gps,
    health,
    manual_destination,
    metrics,
    orbital_catalog,
    overview_adsb,
    overview_clock_settings,
    overview_history,
    overview_link_settings,
    overview_upcoming_pois,
    overview_weather,
    pois,
    route_sigmets,
    routes,
    status,
    ui,
)
from app.api.operator import router as operator_router
from app.api.simulation_run import router as simulation_run_router
from app.core.config import ConfigManager
from app.core.eta_service import initialize_eta_service, shutdown_eta_service
from app.core.limiter import limiter
from app.core.logging import get_logger, setup_logging
from app.core.metrics import set_service_info
from app.live.coordinator import LiveCoordinator
from app.mission import (
    routes_v2 as mission_routes_v2,
)
from app.mission import storage as mission_storage
from app.mission.package.preparation_routes import router as preparation_router
from app.mission.planning.journal import Journal
from app.mission.planning.routes import router as planning_router
from app.mission.planning.service import PlanningService
from app.mission.planning.sources import SourceStore
from app.mission.planning.store import PlanningStore
from app.mission.storage import reconcile_active_legs_on_startup
from app.models.config import SimulationConfig
from app.operator.clock import MissionClock
from app.operator.runtime import OperatorRuntimeBinding
from app.satellites import routes as satellite_routes
from app.services.adsb_fi import AdsbFiProvider
from app.services.aviation_weather.gfs.bridge import GfsBridge
from app.services.aviation_weather.live_encounters import capture_flight_encounters
from app.services.aviation_weather.route_context import select_route_context
from app.services.aviation_weather.route_runtime import RouteSigmetService
from app.services.aviation_weather.route_state import NoticeStore
from app.services.aviation_weather.runtime import AviationWeatherService
from app.services.aviation_weather.settings import AviationSettingsStore
from app.services.aviation_weather.transport import AwcTransport
from app.services.ground_entry_point import (
    maybe_refresh_ground_entry_point_metrics,
    publish_ground_entry_point_metrics,
    refresh_ground_entry_point_metrics,
)
from app.services.manual_destination import ManualDestinationStore
from app.services.orbital_catalog import OrbitalCatalogService
from app.services.overview_adsb_settings import AdsbSettingsStore
from app.services.overview_adsb_traffic import AdsbTrafficService
from app.services.overview_clock_settings import OverviewClockSettingsStore
from app.services.overview_history_prometheus import (
    OverviewHistoryReader,
    resolve_overview_history_prometheus_url,
)
from app.services.overview_history_settings import (
    OverviewHistorySettingsStore,
    resolve_overview_history_window_default,
)
from app.services.overview_link_settings import OverviewLinkSettingsStore
from app.services.overview_weather.acquisitions import WeatherAcquisitionPool
from app.services.overview_weather.admission import WeatherAdmission
from app.services.overview_weather.clock import WeatherClock
from app.services.overview_weather.service import WeatherService
from app.services.overview_weather.settings import WeatherSettingsStore
from app.services.overview_weather.transport import PinnedWeatherTransport
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.services.x_band_selection import XBandSelectionStore
from app.simulation.coordinator import SimulationCoordinator
from app.simulation.run_runtime import SimulationRunRuntime
from app.simulation.run_service import SimulationRunService
from app.simulation.run_wakeup import ReplayWakeup

# Configure structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
json_logs = os.getenv("JSON_LOGS", "true").lower() == "true"
log_file = os.getenv("LOG_FILE")

# Optional flag to disable background updates (useful for tests)
_background_updates_enabled = os.getenv(
    "STARLINK_DISABLE_BACKGROUND_TASKS", "0"
).lower() not in {"1", "true", "yes"}

setup_logging(level=log_level, json_format=json_logs, log_file=log_file)
logger = get_logger(__name__)

# Global simulator instance
_coordinator: SimulationCoordinator | LiveCoordinator | None = None
_background_task = None
_simulation_config = None
_route_manager: RouteManager | None = None
OVERVIEW_HISTORY_SETTINGS_PATH = Path("data/settings/overview-history.json")
OVERVIEW_CLOCK_SETTINGS_PATH = Path("data/settings/overview-clocks.json")
OVERVIEW_ADSB_SETTINGS_PATH = Path("data/settings/overview-adsb.json")
OVERVIEW_WEATHER_SETTINGS_PATH = Path("data/settings/overview-weather.json")
OVERVIEW_LINK_SETTINGS_PATH = Path("data/settings/overview-links.json")
X_BAND_SELECTION_PATH = Path("data/settings/x-band-selection.json")
OVERVIEW_HISTORY_PROMETHEUS_TIMEOUT_SECONDS = 5.0
_overview_history_client: httpx.AsyncClient | None = None
_overview_history_settings_store: OverviewHistorySettingsStore | None = None
_overview_clock_settings_store: OverviewClockSettingsStore | None = None
_overview_link_settings_store: OverviewLinkSettingsStore | None = None
ORBITAL_CATALOG_PATH = Path("data/orbital")


def initialize_orbital_catalog_runtime() -> None:
    app.state.orbital_catalog = OrbitalCatalogService(ORBITAL_CATALOG_PATH)


async def shutdown_orbital_catalog_runtime() -> None:
    service = getattr(app.state, "orbital_catalog", None)
    if service is not None:
        await service.aclose()
        del app.state.orbital_catalog


def should_automatically_refresh_ground_entry_point(
    config: SimulationConfig | None,
) -> bool:
    """Return whether this mode may perform external GEP discovery."""
    return config is not None and config.mode == "live"


def initialize_overview_history_runtime() -> None:
    """Initialize the persistent settings and reader for overview history."""
    global _overview_history_client, _overview_history_settings_store
    _overview_history_settings_store = OverviewHistorySettingsStore(
        OVERVIEW_HISTORY_SETTINGS_PATH,
        default_window_seconds=resolve_overview_history_window_default(),
    )
    overview_history.set_overview_history_settings_store(
        _overview_history_settings_store
    )
    _overview_history_client = httpx.AsyncClient(
        base_url=resolve_overview_history_prometheus_url(),
        timeout=OVERVIEW_HISTORY_PROMETHEUS_TIMEOUT_SECONDS,
    )
    reader = OverviewHistoryReader(
        _overview_history_client,
        get_window_seconds=_overview_history_settings_store.get_window_seconds,
        time_source=time.time,
    )
    app.state.overview_history_reader = reader
    overview_history.set_overview_history_reader(reader.read, reader.invalidate)


def initialize_overview_clock_settings_runtime() -> None:
    """Initialize persistent operational-clock settings for the dashboard."""
    global _overview_clock_settings_store
    _overview_clock_settings_store = OverviewClockSettingsStore(
        OVERVIEW_CLOCK_SETTINGS_PATH,
    )
    overview_clock_settings.set_overview_clock_settings_store(
        _overview_clock_settings_store,
    )
    app.state.overview_clock_settings_store = _overview_clock_settings_store


def initialize_overview_link_settings_runtime() -> None:
    """Initialize persistent visibility settings for Overview data links."""
    global _overview_link_settings_store
    _overview_link_settings_store = OverviewLinkSettingsStore(
        OVERVIEW_LINK_SETTINGS_PATH,
    )
    overview_link_settings.set_overview_link_settings_store(
        _overview_link_settings_store,
    )
    app.state.overview_link_settings_store = _overview_link_settings_store


def initialize_overview_adsb_runtime() -> None:
    store = AdsbSettingsStore(OVERVIEW_ADSB_SETTINGS_PATH)
    app.state.overview_adsb_settings_store = store
    client = httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        timeout=10,
        headers={
            "User-Agent": (
                "starlink-dashboard "
                "(+https://github.com/bcl1713/starlink-dashboard/issues)"
            )
        },
    )
    service = AdsbTrafficService(
        store, AdsbFiProvider(client), time.time, time.monotonic
    )
    app.state.overview_adsb_client = client
    app.state.overview_adsb_service = service
    overview_adsb.set_overview_adsb_runtime(store, service)


def initialize_overview_weather_runtime() -> None:
    """Optional weather construction never connects to the provider."""
    try:
        store = WeatherSettingsStore(OVERVIEW_WEATHER_SETTINGS_PATH)
        app.state.overview_weather_settings_store = store
        clock = WeatherClock()
        pool = WeatherAcquisitionPool(
            PinnedWeatherTransport(clock), WeatherAdmission(clock), clock
        )
        app.state.overview_weather_service = WeatherService(store, pool, clock)
    except Exception:  # noqa: BLE001 - optional weather must not block core startup
        logger.warning_json(
            "Overview weather initialization unavailable", exc_info=True
        )


def initialize_aviation_weather_runtime() -> None:
    """Optional construction creates no provider work or normalization worker."""
    try:
        store = AviationSettingsStore(
            OVERVIEW_WEATHER_SETTINGS_PATH.parent / "aviation-weather.json"
        )
        app.state.aviation_weather_settings_store = store
        app.state.aviation_weather_service = AviationWeatherService(
            store, AwcTransport()
        )
    except Exception:  # noqa: BLE001 - optional weather cannot block core startup
        logger.warning_json(
            "Aviation weather initialization unavailable", exc_info=True
        )
        return
    try:
        app.state.route_sigmet_service = RouteSigmetService(
            app.state.aviation_weather_service,
            NoticeStore(store.path.parent / "route-sigmet-notices.json"),
            lambda: (
                select_route_context(
                    getattr(app.state, "route_manager", None),
                    getattr(app.state, "simulation_run_service", None),
                )
                if getattr(app.state, "route_manager", None) is not None
                else None
            ),
            encounter_provider=lambda context: capture_flight_encounters(
                context, app.state
            ),
        )
    except Exception:  # noqa: BLE001 - optional notices preserve bulletin/core startup
        logger.warning_json("Route SIGMET initialization unavailable", exc_info=True)
    try:
        bridge = GfsBridge(
            store,
            Path(
                os.environ.get(
                    "GFS_ARTIFACT_PATH", str(store.path.parent.parent / "gfs")
                )
            ),
            Path(
                os.environ.get(
                    "GFS_MAILBOX_PATH", str(store.path.parent.parent / "gfs-mailbox")
                )
            ),
        )
        bridge._read_settings()
        app.state.aviation_gfs_bridge = bridge
    except Exception:  # noqa: BLE001 - optional GFS must preserve bulletin/core startup
        logger.warning_json("GFS bridge initialization unavailable", exc_info=True)


async def startup_event():
    """Initialize application on startup."""
    from app.mission.planning.deadlines import start_workers

    start_workers()
    global _coordinator, _background_task, _simulation_config, _route_manager

    try:
        logger.info_json("Initializing Starlink Location Backend")

        # Resolve interrupted writes before any mission, POI, route or runtime reader.
        with mission_storage.get_active_leg_lock():
            Journal(
                mission_storage.MISSIONS_DIR,
                Path("/data/routes"),
                Path("/data/pois.json"),
            ).recover()

        reconciliation = reconcile_active_legs_on_startup()
        logger.info_json(
            "Reconciled persisted Mission V2 active legs at startup",
            extra_fields=reconciliation,
        )

        # Load configuration
        logger.info_json("Loading configuration")
        config_manager = ConfigManager()
        _simulation_config = config_manager.load()
        logger.info_json(
            "Configuration loaded",
            extra_fields={
                "mode": _simulation_config.mode,
                "update_interval": _simulation_config.update_interval_seconds,
                "route_pattern": _simulation_config.route.pattern,
            },
        )

        initialize_overview_history_runtime()
        initialize_overview_clock_settings_runtime()
        app.state.manual_destination_store = ManualDestinationStore(
            Path("data/settings/overview-manual-destination.json")
        )
        initialize_overview_link_settings_runtime()
        app.state.x_band_selection_store = XBandSelectionStore(X_BAND_SELECTION_PATH)
        initialize_orbital_catalog_runtime()
        initialize_overview_adsb_runtime()
        initialize_overview_weather_runtime()
        initialize_aviation_weather_runtime()
        await app.state.overview_adsb_service.start()

        # Initialize coordinator based on configured mode
        active_mode = _simulation_config.mode

        if should_automatically_refresh_ground_entry_point(_simulation_config):
            try:
                entry_point = refresh_ground_entry_point_metrics()
                if entry_point is not None:
                    logger.info_json(
                        "Ground entry point discovered",
                        extra_fields={
                            "city": entry_point.city,
                            "country": entry_point.country,
                        },
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning_json(
                    "Failed to publish ground entry point metrics",
                    extra_fields={"error": str(e)},
                    exc_info=True,
                )
        else:
            publish_ground_entry_point_metrics(None)
        if _simulation_config.mode == "live":
            # Initialize LiveCoordinator for real terminal data
            logger.info_json("Initializing LiveCoordinator for live mode")
            _coordinator = LiveCoordinator(_simulation_config)
            logger.info_json("LiveCoordinator initialized successfully")
            # Set service info with live mode
            set_service_info(version="0.2.0", mode="live")
            # Register Starlink client with GPS module for GPS config API
            gps.set_starlink_client(_coordinator.client)
        else:
            # Initialize SimulationCoordinator for simulation mode
            logger.info_json("Initializing SimulationCoordinator for simulation mode")
            _coordinator = SimulationCoordinator(_simulation_config)
            logger.info_json("SimulationCoordinator initialized successfully")
            # Set service info with simulation mode
            set_service_info(version="0.2.0", mode="simulation")

        logger.info_json(
            "Coordinator initialized",
            extra_fields={
                "uptime_seconds": _coordinator.get_uptime_seconds(),
                "coordinator_type": type(_coordinator).__name__,
                "active_mode": active_mode,
            },
        )

        # Register coordinator with API modules
        app.state.coordinator = _coordinator
        health.set_coordinator(_coordinator)
        status.set_coordinator(_coordinator)
        config.set_coordinator(_coordinator)
        pois.set_coordinator(_coordinator)

        # POI-dependent APIs require this state; constructor failure must abort startup.
        logger.info_json("Initializing POIManager")
        poi_manager = POIManager()
        app.state.poi_manager = poi_manager
        logger.info_json("POIManager injected successfully")

        # ETA calculations are optional; their failure does not remove POI API state.
        logger.info_json("Initializing ETA service")
        try:
            initialize_eta_service(poi_manager)
            logger.info_json("ETA service initialized successfully")
        except Exception as e:  # noqa: BLE001 - ETA is optional
            logger.warning_json(
                "Failed to initialize ETA service",
                extra_fields={"error": str(e)},
                exc_info=True,
            )

        # Initialize Route Manager for KML route handling
        logger.info_json("Initializing Route Manager")
        try:
            owned_sources = SourceStore(
                mission_storage.MISSIONS_DIR, Path("/data/routes")
            )
            _route_manager = RouteManager(
                profile_resolver=owned_sources.resolve_profile
            )
            planning_store = PlanningStore(
                mission_storage.MISSIONS_DIR, _route_manager, poi_manager
            )
            planning_store.recover()
            app.state.planning_service = PlanningService(planning_store)
            from app.mission.itinerary_import.migration import migrate_itinerary_mission

            for existing_mission in mission_storage.list_mission_metadata_v2():
                if existing_mission.metadata.get("itinerary_planning"):
                    migrate_itinerary_mission(existing_mission.id, planning_store)
            from app.mission.itinerary_import.service import ImportService

            app.state.itinerary_import_service = ImportService(
                mission_storage.MISSIONS_DIR, _route_manager, poi_manager
            )
            _route_manager.start_watching()
            # mission_routes_v2, exporter, and package_exporter now use dependency injection via app.state
            app.state.route_manager = _route_manager
            from app.mission.pop_status import PopStatusService
            from app.simulation.pop import SimulationPopObservationProvider

            app.state.pop_status_service = PopStatusService(
                _route_manager,
                _current_runtime_config,
                observation_provider=SimulationPopObservationProvider(
                    _pop_lifecycle_token
                ),
                snapshot_context_provider=_simulation_pop_context,
                poi_manager=poi_manager,
            )
            status.set_pop_service(app.state.pop_status_service)
            if _simulation_config.mode == "simulation":
                _publish_pop_observation(_coordinator.get_current_telemetry())

            # Inject into metrics_export as well
            # from app.api import metrics_export
            # metrics_export.set_route_manager(_route_manager)
            # metrics_export.set_poi_manager(poi_manager)

            # Inject RouteManager into SimulationCoordinator (Phase 5 feature)
            if isinstance(_coordinator, SimulationCoordinator):
                _coordinator.set_route_manager(_route_manager)
                logger.info_json("RouteManager injected into SimulationCoordinator")

            logger.info_json("Route Manager initialized successfully")
        except Exception as e:
            logger.error_json(
                "Failed to initialize Route Manager",
                extra_fields={"error": str(e)},
                exc_info=True,
            )
            raise

        # Initialize Flight State Manager for flight phase and ETA mode tracking
        logger.info_json("Initializing Flight State Manager")
        try:
            from app.services.flight_state import get_flight_state_manager

            flight_state = get_flight_state_manager()
            # Sync existing active route (if any) without forcing reset during startup
            if _route_manager:
                try:
                    active_route = _route_manager.get_active_route()
                    if active_route:
                        flight_state.update_route_context(
                            active_route, auto_reset=False, reason="startup"
                        )
                except Exception as sync_exc:  # noqa: BLE001 - optional flight sync
                    logger.debug_json(
                        "Failed to sync flight state with active route during startup",
                        extra_fields={"error": str(sync_exc)},
                    )
            logger.info_json(
                "Flight State Manager initialized successfully",
                extra_fields={
                    "initial_phase": flight_state.get_status().phase.value,
                    "initial_eta_mode": flight_state.get_status().eta_mode.value,
                },
            )
        except Exception as e:
            logger.error_json(
                "Failed to initialize Flight State Manager",
                extra_fields={"error": str(e)},
                exc_info=True,
            )
            raise

        from app.services.flight_events.lifecycle import FlightEventLifecycle

        app.state.flight_event_lifecycle = FlightEventLifecycle(app.state)
        app.state.flight_event_lifecycle.reconcile(active_mode)
        app.state.apply_runtime_config = _apply_runtime_config

        # Initialize CommKa coverage for Grafana static file serving
        logger.info_json("Initializing CommKa satellite coverage")
        try:
            from app.satellites.kmz_importer import load_commka_coverage

            commka_kmz = Path("app/satellites/assets/CommKa.kmz")
            sat_coverage_dir = Path("data/sat_coverage")
            sat_coverage_dir.mkdir(parents=True, exist_ok=True)

            if commka_kmz.exists():
                result = load_commka_coverage(commka_kmz, sat_coverage_dir)
                if result:
                    logger.info_json(
                        "CommKa coverage initialized for Grafana overlay",
                        extra_fields={"geojson_path": str(result)},
                    )
                else:
                    logger.warning_json("Failed to convert CommKa KMZ to GeoJSON")
            else:
                logger.warning_json(
                    "CommKa KMZ file not found",
                    extra_fields={"expected_path": str(commka_kmz)},
                )
        except Exception as e:  # noqa: BLE001
            logger.warning_json(
                "Failed to initialize CommKa coverage",
                extra_fields={"error": str(e)},
                exc_info=True,
            )

        # Log active mode prominently
        mode_description = (
            "Real Starlink terminal data"
            if active_mode == "live"
            else "Simulated telemetry"
        )
        logger.info_json(
            f"Starlink Location Backend operating in {active_mode.upper()} mode",
            extra_fields={
                "mode": active_mode,
                "mode_description": mode_description,
                "coordinator_type": type(_coordinator).__name__,
            },
        )

        run_service = SimulationRunService(
            SimulationRunRuntime(
                time.monotonic, lambda: datetime.now(UTC), active_mode
            ),
            _route_manager,
            poi_manager,
        )
        if isinstance(_coordinator, SimulationCoordinator):
            run_service.coordinator = _coordinator
        run_service.publish = _publish_replay_telemetry
        app.state.simulation_run_service = run_service
        app.state.operator_live_source = _operator_live_source
        app.state.operator_event_source_factory = _operator_event_sources
        app.state.operator_binding = OperatorRuntimeBinding(
            clock=MissionClock(_operator_mission_now),
            context=_operator_context,
            mission_journals=True,
            operating_context=_operator_operating_context,
        )
        # This optional runtime reports its own failures; it never initializes
        # or replaces a store as a side effect of application startup.
        with app.state.operator_binding.access():
            pass

        from app.core.metrics.lifecycle import MetricsRefreshOwner
        from app.services.flight_state import get_flight_state_manager

        initial_refresh = True

        def refresh_metrics():
            nonlocal initial_refresh
            initial, initial_refresh = initial_refresh, False
            return _refresh_metrics_without_collection(initial)

        owner = MetricsRefreshOwner(
            refresh_metrics,
            background_enabled=_background_updates_enabled,
        )
        from app.services.metrics_changes import mission_metrics_changes

        owner.attach(
            _route_manager,
            poi_manager,
            get_flight_state_manager(),
            _coordinator,
            run_service.runtime,
            mission_metrics_changes,
        )
        app.state.metrics_refresh_owner = owner
        await owner.refresh_without_collection(force=True)

        if _background_updates_enabled:
            from app.mission.active_context_owner import ActiveContextOwner

            context_owner = ActiveContextOwner(
                _route_manager, lambda: _current_runtime_config().mode
            )
            app.state.active_context_owner = context_owner
            await context_owner.start()
            run_service.wakeup = ReplayWakeup()
            logger.info_json("Starting background update task")
            _background_task = asyncio.create_task(_background_update_loop(poi_manager))
        else:
            logger.info_json(
                "Background update task disabled via STARLINK_DISABLE_BACKGROUND_TASKS"
            )

        if (
            _simulation_config.exports.customer_briefing_enabled
            and _background_updates_enabled
        ):
            from app.mission.slide_cache.coordinator import start_runtime

            try:
                app.state.customer_pdf_coordinator = start_runtime(
                    _route_manager, poi_manager
                )
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                logger.warning_json(
                    "Customer PDF background preparation unavailable", exc_info=True
                )

        from types import SimpleNamespace

        from app.mission.package.operations_archive import capture_archive
        from app.mission.package.preparation import ExportPreparationService

        app.state.export_preparation_service = ExportPreparationService(
            _route_manager,
            poi_manager,
            enabled=lambda: ConfigManager()
            .get_config()
            .exports.customer_briefing_enabled,
            archive_capture_owned=lambda mission_id, owner, telemetry_format: capture_archive(
                SimpleNamespace(app=app),
                mission_id,
                owner=owner,
                telemetry_format=telemetry_format,
            ),
        )
        logger.info_json("Starlink Location Backend ready")
    except Exception as e:
        logger.error_json(
            "Failed to initialize application",
            extra_fields={"error": str(e)},
            exc_info=True,
        )
        raise


async def shutdown_event():
    """Drain the complete teardown even if its lifespan waiter is cancelled."""
    from app.core.metrics.lifecycle import drain_work

    await drain_work(asyncio.create_task(_shutdown_resources()))


async def _shutdown_resources():
    """Cleanup on shutdown; owned by the shielded lifespan teardown task."""
    from app.mission.planning.deadlines import shutdown_workers

    await asyncio.to_thread(shutdown_workers)
    operator_binding = getattr(app.state, "operator_binding", None)
    if operator_binding is not None:
        await asyncio.to_thread(operator_binding.close)
        del app.state.operator_binding
    global _background_task, _overview_history_client
    global _overview_history_settings_store, _overview_clock_settings_store, _route_manager
    global _overview_link_settings_store

    try:
        logger.info_json("Shutting down Starlink Location Backend")
        owner = getattr(app.state, "metrics_refresh_owner", None)
        if owner is not None:
            await owner.close()
            del app.state.metrics_refresh_owner
        if _background_task:
            logger.info_json("Cancelling background update task")
            _background_task.cancel()
            try:
                await _background_task
            except asyncio.CancelledError:
                logger.info_json("Background task cancelled successfully")
            _background_task = None

        context_owner = getattr(app.state, "active_context_owner", None)
        if context_owner is not None:
            await context_owner.close()
            del app.state.active_context_owner

        from app.core.metrics.prometheus_metrics import FRAME_STORE

        FRAME_STORE.invalidate("shutdown")

        if hasattr(app.state, "itinerary_import_service"):
            await asyncio.to_thread(app.state.itinerary_import_service.close)
            del app.state.itinerary_import_service
        if hasattr(app.state, "export_preparation_service"):
            await asyncio.to_thread(app.state.export_preparation_service.close)
            del app.state.export_preparation_service
        if hasattr(app.state, "customer_pdf_coordinator"):
            await asyncio.to_thread(app.state.customer_pdf_coordinator.close)
            del app.state.customer_pdf_coordinator
        if hasattr(app.state, "aviation_gfs_bridge"):
            try:
                await app.state.aviation_gfs_bridge.aclose()
            except (OSError, ValueError, TimeoutError):
                logger.warning_json("GFS demand withdrawal unavailable")
            del app.state.aviation_gfs_bridge
        if hasattr(app.state, "route_sigmet_service"):
            await app.state.route_sigmet_service.aclose()
            del app.state.route_sigmet_service
        if hasattr(app.state, "aviation_weather_service"):
            await app.state.aviation_weather_service.aclose()
            del app.state.aviation_weather_service
        if hasattr(app.state, "aviation_weather_settings_store"):
            del app.state.aviation_weather_settings_store
        if hasattr(app.state, "overview_weather_service"):
            await app.state.overview_weather_service.aclose()
            del app.state.overview_weather_service
        if hasattr(app.state, "overview_weather_settings_store"):
            del app.state.overview_weather_settings_store
        if hasattr(app.state, "simulation_run_service"):
            app.state.simulation_run_service.close()
            del app.state.simulation_run_service
        if hasattr(app.state, "overview_adsb_service"):
            await app.state.overview_adsb_service.aclose()
            del app.state.overview_adsb_service
        if hasattr(app.state, "overview_adsb_client"):
            await app.state.overview_adsb_client.aclose()
            del app.state.overview_adsb_client
        overview_adsb.set_overview_adsb_runtime(None, None)
        if hasattr(app.state, "overview_adsb_settings_store"):
            del app.state.overview_adsb_settings_store
        await shutdown_orbital_catalog_runtime()
        overview_history.set_overview_history_reader(None)
        overview_history.set_overview_history_settings_store(None)
        overview_clock_settings.set_overview_clock_settings_store(None)
        if hasattr(app.state, "manual_destination_store"):
            del app.state.manual_destination_store
        overview_link_settings.set_overview_link_settings_store(None)
        if hasattr(app.state, "x_band_selection_store"):
            del app.state.x_band_selection_store
        _overview_link_settings_store = None
        if hasattr(app.state, "overview_link_settings_store"):
            del app.state.overview_link_settings_store
        if hasattr(app.state, "overview_clock_settings_store"):
            del app.state.overview_clock_settings_store
        if hasattr(app.state, "overview_history_reader"):
            await app.state.overview_history_reader.aclose()
            del app.state.overview_history_reader
        lifecycle = getattr(app.state, "flight_event_lifecycle", None)
        if lifecycle is not None:
            lifecycle.close()
            del app.state.flight_event_lifecycle
        elif getattr(app.state, "flight_event_runtime", None) is not None:
            app.state.flight_event_runtime.close()
            app.state.flight_event_runtime = None
        if hasattr(app.state, "apply_runtime_config"):
            del app.state.apply_runtime_config
        if isinstance(_coordinator, LiveCoordinator):
            _coordinator.shutdown()
        gps.set_starlink_client(None)
        if _overview_history_client is not None:
            await _overview_history_client.aclose()
            _overview_history_client = None
        _overview_history_settings_store = None
        _overview_clock_settings_store = None

        if _route_manager:
            logger.info_json("Stopping Route Manager watcher")
            _route_manager.stop_watching()
            _route_manager = None

        # Shutdown ETA service
        logger.info_json("Shutting down ETA service")
        shutdown_eta_service()

        logger.info_json("Shutdown complete")
    except Exception as e:  # noqa: BLE001
        logger.error_json(
            "Error during shutdown", extra_fields={"error": str(e)}, exc_info=True
        )


def _apply_runtime_config(new_config):
    """Called under repository admission: replace source and rebind its owners."""
    global _coordinator, _simulation_config
    previous = _coordinator
    expected = LiveCoordinator if new_config.mode == "live" else SimulationCoordinator
    if isinstance(previous, expected):
        previous.update_config(new_config)
    else:
        replacement = expected(new_config)
        if (
            isinstance(replacement, SimulationCoordinator)
            and _route_manager is not None
        ):
            replacement.set_route_manager(_route_manager)
        owner = getattr(app.state, "metrics_refresh_owner", None)
        if owner is not None:
            owner.detach(previous)
            owner.attach(replacement)
        _coordinator = replacement
        app.state.coordinator = replacement
        for module in (health, status, config, pois):
            module.set_coordinator(replacement)
        gps.set_starlink_client(
            replacement.client if isinstance(replacement, LiveCoordinator) else None
        )
        service = getattr(app.state, "simulation_run_service", None)
        if service is not None:
            service.coordinator = (
                replacement if isinstance(replacement, SimulationCoordinator) else None
            )
        if isinstance(previous, LiveCoordinator):
            previous.shutdown()
    _simulation_config = new_config
    set_service_info(version="0.2.0", mode=new_config.mode)
    lifecycle = getattr(app.state, "flight_event_lifecycle", None)
    if lifecycle is not None:
        lifecycle.reconcile(new_config.mode)
    from app.services.flight_state import get_flight_state_manager

    get_flight_state_manager().reset_detection()
    owner = getattr(app.state, "metrics_refresh_owner", None)
    if owner is not None:
        owner.mark_dirty("Configuration source reconciled")


def _current_runtime_config():
    """Prefer validated current config; legacy adapters use application config."""
    getter = getattr(_coordinator, "get_config", None)
    candidate = getter() if callable(getter) else None
    return candidate if isinstance(candidate, SimulationConfig) else _simulation_config


def _operator_mission_now():
    """Read published replay time without acquiring the repository input gate."""
    service = getattr(app.state, "simulation_run_service", None)
    config = _current_runtime_config()
    if config is None or config.mode != "simulation" or service is None:
        return None
    status = service.status()
    if status.state in ("running", "completed") and status.run is not None:
        return status.run.simulation_time
    return None


def _operator_context():
    config = _current_runtime_config()
    run_service = getattr(app.state, "simulation_run_service", None)
    status = run_service.status() if run_service is not None else None
    run = status.run if status and status.state in ("running", "completed") else None
    return config.mode, run.run_id if run is not None else None


def _operator_operating_context():
    """Identify ordinary activation using the existing replay runtime revision.

    This is a source boundary, not a new mode or persisted session service.
    Paced activity continues to use its actual replay ID. A backend restart
    conservatively requires reporting readiness again; definitions remain usable.
    """
    service = getattr(app.state, "simulation_run_service", None)
    if _current_runtime_config().mode != "simulation" or service is None:
        return None
    status = service.status()
    route_id = _route_manager.get_active_route_id() if _route_manager else None
    if status.state != "idle" or not route_id:
        return None
    return f"ordinary:{status.runtime_id}:{status.revision}:{route_id}"


def _operator_model_context():
    from app.services.flight_state import get_flight_state_manager

    mode, run_id = _operator_context()
    if mode == "simulation":
        run_id = run_id or os.getenv("OPERATOR_SIMULATION_RUN_ID") or None
    flight = get_flight_state_manager().get_status()
    manager = getattr(app.state, "route_manager", None)
    return {
        "source_mode": mode,
        "simulation_run_id": run_id,
        "lifecycle": _pop_lifecycle_token(run_id),
        "active_route_id": manager.get_active_route_id() if manager else None,
        "phase": flight.phase.value,
        "departure_time": flight.departure_time,
        "arrival_time": flight.arrival_time,
    }


def _operator_event_sources(runtime):
    from app.operator.production_event_sources import ProductionEventSources

    def telemetry():
        connected = getattr(_coordinator, "is_connected", None)
        if callable(connected) and not connected():
            return None
        return _coordinator.get_current_telemetry()

    return ProductionEventSources(
        runtime.service,
        clock=runtime.clock,
        publication=runtime.event_publication,
        route_manager=app.state.route_manager,
        poi_manager=app.state.poi_manager,
        config_provider=_current_runtime_config,
        telemetry_provider=telemetry,
        context_provider=_operator_model_context,
        live_provider=_operator_live_source,
        pop_service=app.state.pop_status_service,
    )


def _operator_live_source(mission_id):
    service = getattr(app.state, "pop_status_service", None)
    publication = service.read_publication() if service is not None else None
    if (
        publication
        and publication.get("mission_id") == mission_id
        and publication.get("leg_id")
    ):
        return publication["leg_id"], publication
    return None


def _pop_lifecycle_token(run_id=None):
    service = getattr(app.state, "simulation_run_service", None)
    run = service.status().run if service is not None else None
    return (
        id(_coordinator),
        getattr(_coordinator, "pop_lifecycle_token", 0),
        run_id or (run.run_id if run is not None else None),
    )


def _simulation_pop_context():
    from app.simulation.run_timing import published_replay

    replay = published_replay(getattr(app.state, "simulation_run_service", None))
    context = {
        "lifecycle_token": _pop_lifecycle_token(),
        "simulation_run_id": _operator_context()[1]
        or os.getenv("OPERATOR_SIMULATION_RUN_ID")
        or None,
    }
    if replay is not None:
        plan, frame, _clock = replay
        context.update(
            mission_id=plan.mission_id,
            leg_id=plan.leg_id,
            simulation_run_id=_pop_lifecycle_token()[-1],
            route=plan.artifacts.route,
            call_capabilities=plan.artifacts.call_capabilities,
            projector=plan.artifacts.projector,
            now=frame.simulation_time,
            observed_now=datetime.now(UTC),
            flight_phase=frame.phase.value,
            unavailable_reason=None,
            enabled=plan.starshield_enabled,
        )
    return context


def _publish_pop_observation(telemetry, tick=None):
    """Publish synthetic legacy metrics from the same emitted observation as status."""
    config = _current_runtime_config()
    if config is None or config.mode != "simulation":
        return
    from app.services.pop.catalog import load_catalog
    from app.simulation.pop import SimulationPopObservationProvider

    service = getattr(app.state, "pop_status_service", None)
    if service is None or telemetry is None:
        publish_ground_entry_point_metrics(None)
        return
    try:
        catalog = load_catalog(config.pop.catalog_path)
    except (OSError, ValueError):
        catalog = None
    provider = service.observation_provider
    if isinstance(provider, SimulationPopObservationProvider):
        observation = provider.simulation_observation(
            telemetry,
            catalog,
            lifecycle_token=_pop_lifecycle_token(
                tick.status.run.run_id if tick else None
            ),
        )
    else:
        observation = provider("simulation", telemetry, catalog)
    publish_ground_entry_point_metrics(observation.entry)


def _publish_replay_telemetry(telemetry, tick):
    from app.core.metrics.frame_builder import coordinator_identity
    from app.core.metrics.metric_updater import prepare_metrics_from_telemetry
    from app.simulation.run_timing import mission_time_context

    frame = prepare_metrics_from_telemetry(
        telemetry,
        _current_runtime_config(),
        tick.plan.artifacts.route.model_copy(deep=True),
        app.state.poi_manager,
        mission_context=mission_time_context(tick.status),
        simulation_plan=tick.plan,
        simulation_frame=tick.frame,
        coordinator_id=coordinator_identity(_coordinator),
    )
    _publish_pop_observation(telemetry, tick)
    return frame


def _refresh_metrics_without_collection(initial=False):
    from app.core.metrics.metric_updater import UTC, datetime
    from app.core.metrics.refresh_inputs import refresh_current_metrics

    return refresh_current_metrics(
        lambda: (
            _coordinator,
            _current_runtime_config(),
            _route_manager,
            app.state.poi_manager,
            getattr(app.state, "simulation_run_service", None),
        ),
        initial=initial,
        now=datetime.now(UTC),
    )


def _background_update_tick(poi_manager, refresh_interval, update_count, error_count):
    """One complete ordered telemetry/metric update, owned by the async loop."""
    # Capture the producer binding before collection, including replacements
    # that happen while live transport is blocked outside repository admission.
    from app.core.metrics.frame_builder import coordinator_identity
    from app.core.metrics.frames import GaugeFrame
    from app.core.metrics.prometheus_metrics import FRAME_STORE
    from app.core.metrics.source_admission import (
        frame_inputs_are_current,
        route_source_identity,
    )
    from app.mission.active_context_cache import (
        active_mission_snapshot_is_current,
        get_active_mission_snapshot,
    )
    from app.mission.storage import get_active_leg_lock

    # The lifespan reconciler owns scans in production. Standalone/manual ticks
    # without that owner reconcile on this worker, never on the event loop.
    unmanaged_context = (
        _route_manager is not None
        and _current_runtime_config().mode == "live"
        and not getattr(_route_manager, "_active_mission_context_owner", None)
    )
    if unmanaged_context:
        get_active_mission_snapshot(_route_manager)

    with get_active_leg_lock():
        source_expected = FRAME_STORE.read()
        coordinator = _coordinator
        source_lifecycle = coordinator_identity(coordinator)
        source_routes = _route_manager
        source_route = source_routes.get_active_route() if source_routes else None
        source_route_id = source_routes.get_active_route_id() if source_routes else None
        current_config = _current_runtime_config()
        source_config = (
            current_config.model_dump_json()
            if isinstance(current_config, SimulationConfig)
            else None
        )
        source_route_revision = (
            route_source_identity(source_route) if source_config is not None else None
        )
        source_service = getattr(app.state, "simulation_run_service", None)
        source_status = source_service.status() if source_service is not None else None
        source_revision = (
            (
                getattr(source_status, "runtime_id", None),
                getattr(source_status, "revision", None),
            )
            if source_status
            else None
        )

    source_mission = (
        get_active_mission_snapshot(source_routes, reconcile=False)
        if source_routes is not None and current_config.mode == "live"
        else None
    )

    def source_is_current(frame: GaugeFrame | None = None) -> bool:
        # Legacy adapters use the application fallback configuration and may not
        # expose domain-model/source readers. Runnable sources have a validated
        # SimulationConfig and use all admission checks below.
        if source_config is None:
            return (
                _coordinator is coordinator
                and _current_runtime_config() is current_config
                and (
                    source_mission is None
                    or active_mission_snapshot_is_current(
                        _route_manager, source_mission
                    )
                )
                and (
                    frame is None
                    or frame_inputs_are_current(frame, active_route, poi_manager)
                )
            )
        checked_routes = _route_manager
        checked_route = checked_routes.get_active_route() if checked_routes else None

        current_service = getattr(app.state, "simulation_run_service", None)
        status = current_service.status() if current_service is not None else None
        revision = (
            (getattr(status, "runtime_id", None), getattr(status, "revision", None))
            if status
            else None
        )
        return (
            _coordinator is coordinator
            and coordinator_identity(coordinator) == source_lifecycle
            and _current_runtime_config() is current_config
            and (
                source_config is None
                or current_config.model_dump_json() == source_config
            )
            and current_service is source_service
            and checked_routes is source_routes
            and checked_route is source_route
            and route_source_identity(checked_route) == source_route_revision
            and (checked_routes.get_active_route_id() if checked_routes else None)
            == source_route_id
            and revision == source_revision
            and (
                source_mission is None
                or active_mission_snapshot_is_current(checked_routes, source_mission)
            )
            and (
                coordinator.get_current_telemetry() is telemetry
                if telemetry is not None
                else not getattr(coordinator, "is_connected", lambda: False)()
            )
            and (
                frame is None
                or frame_inputs_are_current(frame, checked_route, poi_manager)
            )
        )

    if should_automatically_refresh_ground_entry_point(current_config):
        publish_ground_entry_point_metrics(
            maybe_refresh_ground_entry_point_metrics(
                refresh_interval_seconds=refresh_interval
            )
        )

    lifecycle = getattr(app.state, "flight_event_lifecycle", None)
    if lifecycle is not None:
        with get_active_leg_lock():
            lifecycle.reconcile(_current_runtime_config().mode)
        lifecycle.tick()
    else:
        runtime = getattr(app.state, "flight_event_runtime", None)
        if runtime is not None:
            try:
                runtime.tick()
            except (OSError, sqlite3.Error, ValueError):
                logger.warning_json("Telemetry archive recovery pending")
    if _coordinator:
        run_service = getattr(app.state, "simulation_run_service", None)
        paced = (
            run_service is not None and run_service.runtime.selected_plan() is not None
        )
        try:
            previous_telemetry = getattr(
                coordinator, "get_current_telemetry", lambda: None
            )()
        except RuntimeError:
            previous_telemetry = None
        telemetry = (
            run_service.collect(_coordinator, _publish_replay_telemetry)
            if paced
            else coordinator.update()
        )
        if not paced:
            _publish_pop_observation(telemetry)
        update_count += 1
        if unmanaged_context:
            # A slow unowned acquisition may cross the reconciliation schedule.
            # Expiry schedules a check; it does not itself change source identity.
            get_active_mission_snapshot(source_routes)

        # Retained acquisition: refresh planned values and freshness without
        # observation accounting, source generation, or detection side effects.
        if telemetry is not None and telemetry is previous_telemetry and not paced:
            with get_active_leg_lock():
                active_route = (
                    _route_manager.get_active_route() if _route_manager else None
                )
                if source_is_current():
                    _refresh_metrics_without_collection()
                else:
                    FRAME_STORE.fail(source_expected, "retained source superseded")
            return update_count

        # Only update metrics if telemetry is available
        # In live mode, telemetry will be None when disconnected
        if telemetry is not None and not paced:
            # Track metric collection duration
            from app.core.metrics import (
                starlink_metrics_generation_errors_total,
                starlink_metrics_scrape_duration_seconds,
            )
            from app.core.metrics.metric_updater import (
                _update_metrics_from_telemetry_admitted,
            )

            scrape_start = time.time()
            try:
                with get_active_leg_lock():
                    # Both live and simulation metrics use the application's
                    # current route, independent of coordinator capabilities.
                    active_route = source_route
                    # Snapshot progress before immediate admission validation;
                    # its reader may change the source binding.
                    route_progress = (
                        getattr(coordinator, "route_progress_snapshot", lambda: None)()
                        if current_config.mode == "simulation"
                        else None
                    )

                    flight_events_managed = current_config.mode == "live"
                    runtime = getattr(app.state, "flight_event_runtime", None)
                    live_events = runtime is not None and current_config.mode == "live"
                    if not source_is_current():
                        FRAME_STORE.fail(
                            source_expected, "source changed during collection"
                        )
                        return update_count

                    if live_events:
                        from app.services.flight_state import get_flight_state_manager

                        snapshot = source_mission
                        context = snapshot.binding if snapshot is not None else None
                        flight_events_managed = True
                        if lifecycle is not None:
                            lifecycle.process_live(
                                telemetry,
                                context,
                                get_flight_state_manager(),
                                source_is_current,
                            )
                        else:
                            # Compatibility for isolated adapters without an app lifespan.
                            try:
                                runtime.record_live(telemetry)
                            except (OSError, sqlite3.Error, ValueError):
                                logger.warning_json("Live sample recording unavailable")
                            try:
                                if context is not None and source_is_current():
                                    runtime.observe_live(telemetry, context)
                                    if source_is_current():
                                        runtime.sync_legacy_phase(
                                            get_flight_state_manager(),
                                            context.parent_mission_id,
                                            context.leg.id,
                                        )
                            except (OSError, sqlite3.Error, ValueError):
                                logger.warning_json("Live flight detection unavailable")
                        # Event handling (including caught recording failures)
                        # may replace inputs. Keep its distinct entry boundary.
                        if not source_is_current():
                            return update_count
                    _update_metrics_from_telemetry_admitted(
                        telemetry,
                        current_config,
                        active_route,
                        poi_manager,
                        flight_events_managed=flight_events_managed,
                        route_progress=route_progress,
                        coordinator_id=source_lifecycle,
                        final_validation=source_is_current,
                    )
                    scrape_duration = time.time() - scrape_start
                    starlink_metrics_scrape_duration_seconds.observe(scrape_duration)
            except Exception as metric_error:  # noqa: BLE001
                starlink_metrics_generation_errors_total.inc()
                logger.warning_json(
                    "Error updating metrics",
                    extra_fields={"error": str(metric_error)},
                    exc_info=True,
                )

            # Log periodic updates (every 60 seconds)
            if update_count % 600 == 0:
                logger.info_json(
                    "Background updates running",
                    extra_fields={
                        "total_updates": update_count,
                        "total_errors": error_count,
                        "position": {
                            "lat": telemetry.position.latitude,
                            "lon": telemetry.position.longitude,
                        },
                        "network_latency_ms": telemetry.network.latency_ms,
                    },
                )
        elif telemetry is None:
            # Clear metrics when disconnected to prevent stale data
            # This sets all telemetry metrics to NaN, which Prometheus won't store
            from app.core.metrics import clear_telemetry_metrics

            with get_active_leg_lock():
                active_route = (
                    _route_manager.get_active_route() if _route_manager else None
                )
                if source_is_current():
                    from app.core.metrics import update_metrics_from_telemetry

                    update_metrics_from_telemetry(None)
                    clear_telemetry_metrics(
                        config=current_config,
                        active_route=active_route,
                        poi_manager=poi_manager,
                        coordinator_id=source_lifecycle,
                    )
                else:
                    FRAME_STORE.fail(
                        source_expected, "source changed during disconnect"
                    )

            # Log when disconnected (less frequently to avoid spam)
            if update_count % 600 == 0:
                logger.info_json(
                    "Live mode: waiting for dish connection",
                    extra_fields={
                        "total_updates": update_count,
                        "total_errors": error_count,
                    },
                )

    return update_count


async def _background_update_loop(poi_manager=None):
    """Background task that updates simulator every interval."""
    update_count = 0
    error_count = 0
    try:
        ground_entry_refresh_interval_seconds = float(
            os.getenv("STARLINK_GROUND_ENTRY_REFRESH_SECONDS", "1")
        )
    except ValueError:
        ground_entry_refresh_interval_seconds = 1.0
        logger.warning_json(
            "Invalid STARLINK_GROUND_ENTRY_REFRESH_SECONDS; using default",
            extra_fields={"value": os.getenv("STARLINK_GROUND_ENTRY_REFRESH_SECONDS")},
        )

    try:
        logger.info_json("Background update loop started")

        while True:
            try:
                work = asyncio.create_task(
                    asyncio.to_thread(
                        _background_update_tick,
                        poi_manager,
                        ground_entry_refresh_interval_seconds,
                        update_count,
                        error_count,
                    )
                )
                try:
                    update_count = await asyncio.shield(work)
                except asyncio.CancelledError:
                    # Shield keeps the worker owned; drain before shutting down managers.
                    while not work.done():
                        try:
                            await asyncio.gather(
                                asyncio.shield(work), return_exceptions=True
                            )
                        except asyncio.CancelledError:
                            continue
                    raise

                # Sleep for configured update interval
                run_service = getattr(app.state, "simulation_run_service", None)
                delay = (
                    run_service.runtime.seconds_until_next_tick()
                    if run_service and run_service.status().state == "running"
                    else _simulation_config.update_interval_seconds
                )
                owner = getattr(app.state, "metrics_refresh_owner", None)
                if owner is not None and _background_updates_enabled:
                    deadline = asyncio.get_running_loop().time() + delay
                    while not await owner.wait(
                        deadline - asyncio.get_running_loop().time(),
                        run_service.wakeup if run_service else None,
                    ):
                        await owner.refresh_without_collection()
                elif run_service and run_service.wakeup:
                    await run_service.wakeup.wait(delay)
                else:
                    await asyncio.sleep(delay)

            except Exception as e:  # noqa: BLE001
                error_count += 1
                logger.warning_json(
                    "Error in background update",
                    extra_fields={
                        "error": str(e),
                        "error_count": error_count,
                        "update_count": update_count,
                    },
                    exc_info=True,
                )

                from app.core.metrics import simulation_errors_total

                simulation_errors_total.inc()

                # Continue running on error with backoff
                await asyncio.sleep(1.0)

    except asyncio.CancelledError:
        logger.info_json(
            "Background update task cancelled",
            extra_fields={"total_updates": update_count, "total_errors": error_count},
        )
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    try:
        await startup_event()
        yield
    finally:
        await shutdown_event()


# Create FastAPI application
app = FastAPI(
    title="Starlink Location Backend",
    description="Prometheus-compatible metrics exporter and telemetry API for Starlink simulator",
    version="0.2.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "Idempotency-Replayed", "ETag"],
)

# Mount data/sat_coverage directory for satellite coverage overlays (Ka/CommKa GeoJSON)
# This enables Grafana to access coverage footprints via HTTP at /data/sat_coverage/commka.geojson
# instead of requiring direct filesystem access across Docker container boundaries
sat_coverage_dir = Path("data/sat_coverage")
sat_coverage_dir.mkdir(parents=True, exist_ok=True)
try:
    app.mount(
        "/data/sat_coverage",
        StaticFiles(directory=str(sat_coverage_dir)),
        name="sat_coverage",
    )
    logger.info_json(
        "Mounted static files for satellite coverage at /data/sat_coverage"
    )
except Exception as e:  # noqa: BLE001 - optional static mount must not block API import
    logger.warning_json(
        "Failed to mount satellite coverage static files",
        extra_fields={"error": str(e)},
        exc_info=True,
    )


# Exception handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle generic exceptions with JSON response."""
    logger.error_json(
        "Unhandled exception in request",
        extra_fields={
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
            "error": str(exc),
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_type": type(exc).__name__},
    )


# Register API routers
from app.api.flight_events import router as flight_events_router

app.include_router(flight_events_router)
app.include_router(simulation_run_router)
app.include_router(operator_router)
app.include_router(health.router, tags=["Health"])
app.include_router(metrics.router, tags=["Metrics"])
app.include_router(active_x_link.router, tags=["Active X Link"])
app.include_router(status.router, tags=["Status"])
app.include_router(overview_clock_settings.router, tags=["Overview Clocks"])
app.include_router(overview_link_settings.router, tags=["Overview Links"])
app.include_router(overview_adsb.router, tags=["ADS-B Aircraft"])
app.include_router(orbital_catalog.router, tags=["Orbital Experiment"])
app.include_router(overview_history.router, tags=["Overview History"])
app.include_router(overview_upcoming_pois.router, tags=["Overview POIs"])
app.include_router(manual_destination.router)
app.include_router(config.router, tags=["Configuration"])
app.include_router(flight_status.router, tags=["Flight Status"])
app.include_router(geojson.router, tags=["GeoJSON"])
app.include_router(pois.router, tags=["POIs"])
app.include_router(routes.router, tags=["Routes"])
app.include_router(planning_router)
app.include_router(preparation_router)
from app.mission.itinerary_import.routes import router as itinerary_import_router

app.include_router(itinerary_import_router)
app.include_router(mission_routes_v2.router, tags=["Missions V2"])
app.include_router(satellite_routes.router, tags=["Satellites"])
app.include_router(export.router, tags=["Export"])
app.include_router(gps.router, tags=["GPS"])
app.include_router(overview_weather.router, tags=["Overview Weather"])
app.include_router(aviation_weather.router, tags=["Aviation Weather"])
app.include_router(route_sigmets.router, tags=["Aviation Weather"])
app.include_router(ui.router, tags=["UI"])


@app.get("/")
async def root():
    """
    Root endpoint with API documentation.

    Returns a welcome message and links to API documentation.
    """
    return {
        "message": "Starlink Location Backend",
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "status": "/api/status",
            "config": "/api/config",
            "position.geojson": "/api/position.geojson",
            "route.geojson": "/api/route.geojson",
            "pois.geojson": "/api/pois.geojson",
            "route.json": "/api/route.json",
        },
    }
