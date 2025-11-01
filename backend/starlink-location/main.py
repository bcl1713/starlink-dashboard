"""Starlink Location Backend - FastAPI Application."""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import config, geojson, health, metrics, pois, routes, status, ui
from app.core.config import ConfigManager
from app.core.eta_service import initialize_eta_service, shutdown_eta_service
from app.core.logging import setup_logging, get_logger
from app.core.metrics import set_service_info
from app.live.coordinator import LiveCoordinator
from app.simulation.coordinator import SimulationCoordinator
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

# Configure structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
json_logs = os.getenv("JSON_LOGS", "true").lower() == "true"
log_file = os.getenv("LOG_FILE")

setup_logging(level=log_level, json_format=json_logs, log_file=log_file)
logger = get_logger(__name__)

# Global simulator instance
_coordinator: SimulationCoordinator = None
_background_task = None
_simulation_config = None
_route_manager: RouteManager = None


async def startup_event():
    """Initialize application on startup."""
    global _coordinator, _background_task, _simulation_config, _route_manager

    try:
        logger.info_json("Initializing Starlink Location Backend")

        # Load configuration
        logger.info_json("Loading configuration")
        config_manager = ConfigManager()
        _simulation_config = config_manager.load()
        logger.info_json(
            "Configuration loaded",
            extra_fields={
                "mode": _simulation_config.mode,
                "update_interval": _simulation_config.update_interval_seconds,
                "route_pattern": _simulation_config.route.pattern
            }
        )

        # Initialize coordinator based on configured mode
        active_mode = _simulation_config.mode

        if _simulation_config.mode == "live":
            # Initialize LiveCoordinator for real terminal data
            logger.info_json("Initializing LiveCoordinator for live mode")
            _coordinator = LiveCoordinator(_simulation_config)
            logger.info_json("LiveCoordinator initialized successfully")
            # Set service info with live mode
            set_service_info(version="0.2.0", mode="live")
        else:
            # Initialize SimulationCoordinator for simulation mode
            logger.info_json("Initializing SimulationCoordinator for simulation mode")
            _coordinator = SimulationCoordinator(_simulation_config)
            logger.info_json("SimulationCoordinator initialized successfully")
            # Set service info with simulation mode
            set_service_info(version="0.2.0", mode="simulation")

        logger.info_json(
            f"Coordinator initialized",
            extra_fields={
                "uptime_seconds": _coordinator.get_uptime_seconds(),
                "coordinator_type": type(_coordinator).__name__,
                "active_mode": active_mode
            }
        )

        # Register coordinator with API modules
        health.set_coordinator(_coordinator)
        status.set_coordinator(_coordinator)
        config.set_coordinator(_coordinator)
        pois.set_coordinator(_coordinator)

        # Initialize ETA service for POI calculations
        logger.info_json("Initializing ETA service")
        try:
            poi_manager = POIManager()
            initialize_eta_service(poi_manager)
            logger.info_json("ETA service initialized successfully")
        except Exception as e:
            logger.warning_json(
                "Failed to initialize ETA service",
                extra_fields={"error": str(e)},
                exc_info=True
            )

        # Inject POIManager singleton into all API modules
        logger.info_json("Injecting POIManager into API modules")
        try:
            pois.set_poi_manager(poi_manager)
            routes.set_poi_manager(poi_manager)
            geojson.set_poi_manager(poi_manager)
            # Note: metrics_export also gets POIManager but via route_manager injection below
            logger.info_json("POIManager injected successfully")
        except Exception as e:
            logger.warning_json(
                "Failed to inject POIManager",
                extra_fields={"error": str(e)},
                exc_info=True
            )

        # Initialize Route Manager for KML route handling
        logger.info_json("Initializing Route Manager")
        try:
            _route_manager = RouteManager()
            _route_manager.start_watching()
            geojson.set_route_manager(_route_manager)
            routes.set_route_manager(_route_manager)
            # Inject into metrics_export as well
            from app.api import metrics_export
            metrics_export.set_route_manager(_route_manager)
            metrics_export.set_poi_manager(poi_manager)
            logger.info_json("Route Manager initialized successfully")
        except Exception as e:
            logger.error_json(
                "Failed to initialize Route Manager",
                extra_fields={"error": str(e)},
                exc_info=True
            )
            raise

        # Log active mode prominently
        mode_description = "Real Starlink terminal data" if active_mode == "live" else "Simulated telemetry"
        logger.info_json(
            f"Starlink Location Backend operating in {active_mode.upper()} mode",
            extra_fields={
                "mode": active_mode,
                "mode_description": mode_description,
                "coordinator_type": type(_coordinator).__name__
            }
        )

        # Start background update task
        logger.info_json("Starting background update task")
        _background_task = asyncio.create_task(_background_update_loop())

        logger.info_json("Starlink Location Backend ready")
    except Exception as e:
        logger.error_json(
            "Failed to initialize application",
            extra_fields={"error": str(e)},
            exc_info=True
        )
        raise


async def shutdown_event():
    """Cleanup on shutdown."""
    global _background_task

    try:
        logger.info_json("Shutting down Starlink Location Backend")

        if _background_task:
            logger.info_json("Cancelling background update task")
            _background_task.cancel()
            try:
                await _background_task
            except asyncio.CancelledError:
                logger.info_json("Background task cancelled successfully")

        # Shutdown ETA service
        logger.info_json("Shutting down ETA service")
        shutdown_eta_service()

        logger.info_json("Shutdown complete")
    except Exception as e:
        logger.error_json(
            "Error during shutdown",
            extra_fields={"error": str(e)},
            exc_info=True
        )


async def _background_update_loop():
    """Background task that updates simulator every interval."""
    global _coordinator, _simulation_config

    update_count = 0
    error_count = 0

    try:
        logger.info_json("Background update loop started")

        while True:
            try:
                if _coordinator:
                    telemetry = _coordinator.update()
                    update_count += 1

                    # Only update metrics if telemetry is available
                    # In live mode, telemetry will be None when disconnected
                    if telemetry is not None:
                        # Track metric collection duration
                        from app.core.metrics import (
                            update_metrics_from_telemetry,
                            starlink_metrics_scrape_duration_seconds,
                            starlink_metrics_last_update_timestamp_seconds,
                            starlink_metrics_generation_errors_total
                        )

                        scrape_start = time.time()
                        try:
                            update_metrics_from_telemetry(telemetry, _simulation_config)
                            scrape_duration = time.time() - scrape_start
                            starlink_metrics_scrape_duration_seconds.observe(scrape_duration)
                            starlink_metrics_last_update_timestamp_seconds.set(time.time())
                        except Exception as metric_error:
                            starlink_metrics_generation_errors_total.inc()
                            logger.warning_json(
                                "Error updating metrics",
                                extra_fields={"error": str(metric_error)},
                                exc_info=True
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
                                        "lon": telemetry.position.longitude
                                    },
                                    "network_latency_ms": telemetry.network.latency_ms
                                }
                            )
                    else:
                        # Clear metrics when disconnected to prevent stale data
                        # This sets all telemetry metrics to NaN, which Prometheus won't store
                        from app.core.metrics import clear_telemetry_metrics
                        clear_telemetry_metrics()

                        # Log when disconnected (less frequently to avoid spam)
                        if update_count % 600 == 0:
                            logger.info_json(
                                "Live mode: waiting for dish connection",
                                extra_fields={
                                    "total_updates": update_count,
                                    "total_errors": error_count
                                }
                            )

                # Sleep for configured update interval
                await asyncio.sleep(_simulation_config.update_interval_seconds)

            except Exception as e:
                error_count += 1
                logger.warning_json(
                    "Error in background update",
                    extra_fields={
                        "error": str(e),
                        "error_count": error_count,
                        "update_count": update_count
                    },
                    exc_info=True
                )

                from app.core.metrics import simulation_errors_total
                simulation_errors_total.inc()

                # Continue running on error with backoff
                await asyncio.sleep(1.0)

    except asyncio.CancelledError:
        logger.info_json(
            "Background update task cancelled",
            extra_fields={
                "total_updates": update_count,
                "total_errors": error_count
            }
        )
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    await startup_event()
    yield
    await shutdown_event()


# Create FastAPI application
app = FastAPI(
    title="Starlink Location Backend",
    description="Prometheus-compatible metrics exporter and telemetry API for Starlink simulator",
    version="0.2.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
            "error": str(exc)
        },
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_type": type(exc).__name__}
    )


# Register API routers
app.include_router(health.router, tags=["Health"])
app.include_router(metrics.router, tags=["Metrics"])
app.include_router(status.router, tags=["Status"])
app.include_router(config.router, tags=["Configuration"])
app.include_router(geojson.router, tags=["GeoJSON"])
app.include_router(pois.router, tags=["POIs"])
app.include_router(routes.router, tags=["Routes"])
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
            "route.json": "/api/route.json"
        }
    }
