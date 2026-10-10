"""Route manager with file watching for KML route loading and management."""

# FR-004: File exceeds 300 lines (330 lines) because route manager combines
# file watching, KML parsing, route storage, and active route coordination.
# Splitting would fragment route lifecycle management. Deferred to v0.4.0.

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from app.models.route import ParsedRoute
from app.services.kml_parser import KMLParseError, parse_kml_file
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class RouteChangeHandler(FileSystemEventHandler):
    """Handles file system events for route directory changes."""

    def __init__(self, route_manager: "RouteManager"):
        self.route_manager = route_manager

    def on_created(self, event):
        """Handle new files in routes directory."""
        if getattr(event, "is_dir", False):
            return
        if event.src_path.lower().endswith(".kml"):
            logger.info(f"New KML file detected: {event.src_path}")
            self.route_manager._load_route_file(event.src_path)

    def on_deleted(self, event):
        """Handle deleted files in routes directory."""
        if getattr(event, "is_dir", False):
            return
        if event.src_path.lower().endswith(".kml"):
            route_id = Path(event.src_path).stem
            logger.info(f"KML file deleted: {event.src_path}, route_id: {route_id}")
            self.route_manager._remove_route(route_id)

    def on_modified(self, event):
        """Handle modified files in routes directory."""
        if getattr(event, "is_dir", False):
            return
        if event.src_path.lower().endswith(".kml"):
            logger.info(f"KML file modified: {event.src_path}")
            self.route_manager._load_route_file(event.src_path)


class RouteManager:
    """
    Manages KML routes with file watching capabilities.

    Features:
    - Watches /data/routes/ directory for new/modified/deleted KML files
    - Maintains in-memory route cache
    - Tracks active route
    - Handles errors gracefully
    """

    def __init__(
        self,
        routes_dir: str | Path = "/data/routes",
        *,
        profile_resolver: (
            Callable[[str], Literal["legacy", "planning_v1"]] | None
        ) = None,
    ):
        self.routes_dir = Path(routes_dir)
        self.routes_dir.mkdir(parents=True, exist_ok=True)

        self._profile_resolver = profile_resolver
        self._routes: dict[str, ParsedRoute] = {}
        self._active_route_id: str | None = None
        self._observer: Observer | None = None
        self._errors: dict[str, str] = {}  # Tracks errors by route_id

        logger.info(f"RouteManager initialized with directory: {self.routes_dir}")

    def start_watching(self) -> None:
        """Start watching the routes directory for file changes."""
        if self._observer is not None:
            logger.warning("RouteManager is already watching")
            return

        # Load existing routes
        self._load_existing_routes()

        # Start file system observer
        self._observer = Observer()
        event_handler = RouteChangeHandler(self)
        self._observer.schedule(event_handler, str(self.routes_dir), recursive=False)
        self._observer.start()

        logger.info("RouteManager started watching for KML files")

    def stop_watching(self) -> None:
        """Stop watching the routes directory."""
        if self._observer is None:
            return

        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None

        logger.info("RouteManager stopped watching")

    def _load_existing_routes(self) -> None:
        """Load all existing KML files from routes directory."""
        if not self.routes_dir.exists():
            logger.warning(f"Routes directory does not exist: {self.routes_dir}")
            return

        for kml_file in self.routes_dir.glob("*.kml"):
            self._load_route_file(str(kml_file))

    def resolve_ingestion_profile(
        self, route_id: str
    ) -> Literal["legacy", "planning_v1"]:
        """Resolve durable ownership before parsing; invalid profiles fail closed.

        Task-owned inventory providers must return an explicit profile, returning
        legacy only for known unmanaged routes. Missing managed descriptors raise
        KMLParseError. Install the provider before start_watching/reload.
        """
        resolver = getattr(self, "_profile_resolver", None)
        profile = resolver(route_id) if resolver else "legacy"
        if profile not in ("legacy", "planning_v1"):
            raise KMLParseError(
                "Missing or unknown route ingestion profile; explicit migration required"
            )
        return profile

    def _load_route_file(self, file_path: str) -> None:
        """
        Load a single KML file and add to routes cache.

        Args:
            file_path: Path to KML file
        """
        route_id = Path(file_path).stem

        try:
            profile = self.resolve_ingestion_profile(route_id)
            parsed_route = (
                parse_kml_file(file_path, profile=profile)
                if profile != "legacy"
                else parse_kml_file(file_path)
            )
            from app.mission.storage import get_active_leg_lock

            with get_active_leg_lock():
                if self.resolve_ingestion_profile(route_id) != profile:
                    raise KMLParseError("Route profile changed during parsing")
                if profile == "planning_v1":
                    import hashlib

                    if (
                        hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
                        != parsed_route.content_hash
                    ):
                        raise KMLParseError("Route content changed during parsing")
                self._routes[route_id] = parsed_route
            # Clear any previous error for this route
            if route_id in self._errors:
                del self._errors[route_id]
            logger.info(
                f"Loaded route: {route_id} with {len(parsed_route.points)} points"
            )
            if self._active_route_id == route_id:
                try:
                    from app.services.flight_state import (
                        get_flight_state_manager,
                    )

                    get_flight_state_manager().update_route_context(
                        parsed_route, auto_reset=False, reason="route_reloaded"
                    )
                except (
                    RuntimeError,
                    ValueError,
                    OSError,
                    KeyError,
                    TypeError,
                    AttributeError,
                    LookupError,
                    ConnectionError,
                    TimeoutError,
                    ImportError,
                    EOFError,
                ) as exc:  # pragma: no cover - defensive guard
                    logger.debug("Failed to sync flight state on route reload: %s", exc)
        except KMLParseError as e:
            error_msg = str(e)
            self._routes.pop(route_id, None)
            self._errors[route_id] = error_msg
            logger.warning(f"Failed to parse KML file {file_path}: {error_msg}")
        except (
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as e:
            error_msg = f"Unexpected error parsing {file_path}: {e}"
            self._routes.pop(route_id, None)
            self._errors[route_id] = error_msg
            logger.error(error_msg)

    def add_route(self, route_id: str, parsed_route: ParsedRoute) -> None:
        """
        Register a ParsedRoute in the manager cache.

        This helper is used by the upload API to ensure a route is immediately
        available even if filesystem watchers miss an event.
        """
        self._routes[route_id] = parsed_route
        if route_id in self._errors:
            del self._errors[route_id]
        logger.info(
            f"Registered route: {route_id} with {len(parsed_route.points)} points via add_route()"
        )

    def _remove_route(self, route_id: str) -> None:
        """
        Remove a route from cache.

        Args:
            route_id: Route identifier (filename without .kml extension)
        """
        if route_id in self._routes:
            del self._routes[route_id]
            logger.info(f"Removed route: {route_id}")

        if route_id in self._errors:
            del self._errors[route_id]

        # Clear active route if it was the deleted one
        if self._active_route_id == route_id:
            self._active_route_id = None
            logger.info("Cleared active route due to deletion")
            try:
                from app.services.flight_state import get_flight_state_manager

                get_flight_state_manager().clear_route_context(reason="route_removed")
            except (
                RuntimeError,
                ValueError,
                OSError,
                KeyError,
                TypeError,
                AttributeError,
                LookupError,
                ConnectionError,
                TimeoutError,
                ImportError,
                EOFError,
            ) as exc:  # pragma: no cover - defensive guard
                logger.debug(
                    "Failed to clear flight state after route removal: %s", exc
                )

    def list_routes(self) -> dict[str, dict]:
        """
        Get list of available routes.

        Returns:
            Dictionary mapping route_id to route info
        """
        result = {}
        for route_id in tuple(self._routes):
            route = self.get_route(route_id)
            if route is None:
                continue
            result[route_id] = {
                "id": route_id,
                "name": route.metadata.name,
                "description": route.metadata.description,
                "point_count": len(route.points),
                "is_active": route_id == self._active_route_id,
                "imported_at": route.metadata.imported_at.isoformat(),
            }

        return result

    def get_route(self, route_id: str) -> ParsedRoute | None:
        """
        Get a specific route by ID.

        Args:
            route_id: Route identifier

        Returns:
            ParsedRoute or None if not found
        """
        if getattr(self, "_profile_resolver", None):
            try:
                self.resolve_ingestion_profile(route_id)
            except KMLParseError as exc:
                self._routes.pop(route_id, None)
                self._errors[route_id] = str(exc)
                return None
        return self._routes.get(route_id)

    def get_active_route_id(self) -> str | None:
        """Return the manager's active route ID without inspecting route metadata."""
        return self._active_route_id

    def get_active_route(self) -> ParsedRoute | None:
        """
        Get the currently active route.

        Returns:
            ParsedRoute or None if no active route
        """
        if self._active_route_id is None:
            return None
        return self.get_route(self._active_route_id)

    def activate_route(self, route_id: str) -> bool:
        """
        Activate a route.

        Args:
            route_id: Route identifier

        Returns:
            True if activation successful, False if route not found or already active
        """
        if self.get_route(route_id) is None:
            logger.warning(f"Cannot activate non-existent route: {route_id}")
            return False

        if self._active_route_id == route_id:
            logger.debug(f"Route {route_id} is already active")
            return False

        self._active_route_id = route_id
        logger.info(f"Activated route: {route_id}")

        try:
            from app.services.flight_state import get_flight_state_manager

            parsed_route = self._routes.get(route_id)
            if parsed_route:
                get_flight_state_manager().update_route_context(
                    parsed_route, auto_reset=True, reason="route_activated"
                )
        except (
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as exc:  # pragma: no cover - defensive guard
            logger.debug("Failed to sync flight state on route activation: %s", exc)
        return True

    def deactivate_route(self, route_id: str | None = None) -> None:
        """Deactivate a specific route or the current active route.

        Args:
            route_id: Route ID to deactivate. If None, deactivates the current active route.
        """
        # If specific route_id provided, only deactivate if it's the active route
        if route_id is not None:
            if self._active_route_id == route_id:
                logger.info(f"Deactivated route: {route_id}")
                self._active_route_id = None
                try:
                    from app.services.flight_state import (
                        get_flight_state_manager,
                    )

                    get_flight_state_manager().clear_route_context(
                        reason="route_deactivated"
                    )
                except (
                    RuntimeError,
                    ValueError,
                    OSError,
                    KeyError,
                    TypeError,
                    AttributeError,
                    LookupError,
                    ConnectionError,
                    TimeoutError,
                    ImportError,
                    EOFError,
                ) as exc:  # pragma: no cover - defensive guard
                    logger.debug(
                        "Failed to clear flight state on route deactivation: %s", exc
                    )
            else:
                logger.debug(f"Route {route_id} is not active, skipping deactivation")
        else:
            # Deactivate current active route
            if self._active_route_id:
                logger.info(f"Deactivated route: {self._active_route_id}")
                try:
                    from app.services.flight_state import (
                        get_flight_state_manager,
                    )

                    get_flight_state_manager().clear_route_context(
                        reason="route_deactivated"
                    )
                except (
                    RuntimeError,
                    ValueError,
                    OSError,
                    KeyError,
                    TypeError,
                    AttributeError,
                    LookupError,
                    ConnectionError,
                    TimeoutError,
                    ImportError,
                    EOFError,
                ) as exc:  # pragma: no cover - defensive guard
                    logger.debug(
                        "Failed to clear flight state on route deactivation: %s", exc
                    )
            self._active_route_id = None

    def get_route_errors(self) -> dict[str, str]:
        """
        Get list of routes that failed to load.

        Returns:
            Dictionary mapping route_id to error message
        """
        return self._errors.copy()

    def has_errors(self) -> bool:
        """Check if any routes failed to load."""
        return len(self._errors) > 0

    def reload_all_routes(self) -> None:
        """Reload all routes from disk."""
        self._routes.clear()
        self._errors.clear()
        self._active_route_id = None
        self._load_existing_routes()
        logger.info("Reloaded all routes from disk")
        try:
            from app.services.flight_state import get_flight_state_manager

            get_flight_state_manager().clear_route_context(reason="routes_reloaded")
        except (
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as exc:  # pragma: no cover - defensive guard
            logger.debug("Failed to clear flight state after route reload: %s", exc)
