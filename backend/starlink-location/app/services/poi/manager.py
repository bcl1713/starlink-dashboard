"""POI manager for loading, saving, and managing points of interest."""

# FR-004: File exceeds 300 lines (961 lines) because POI management combines
# file I/O, locking, JSON parsing, geospatial queries, and in-memory caching
# that are tightly coupled. Separation would split single responsibility across
# multiple modules with reduced cohesion. Deferred to v0.4.0.

import json
import logging
import os
import re
import threading
import uuid
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

from app.models.poi import POI, POICreate, POIUpdate

logger = logging.getLogger(__name__)

COALESCE_INTERVAL_SECONDS = 0.1
MUTATION_ERRORS = (
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
)


@dataclass
class _QueuedOperation:
    """A synchronous POI mutation waiting for the elected writer."""

    name: str
    apply: Callable[[dict[str, POI]], Any]
    completed: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None


class POIManager:
    """
    Manages POI storage and retrieval from JSON file.

    Features:
    - Load/save POIs from `/data/pois.json`
    - Support for global and route-specific POIs
    - Full CRUD operations
    - Automatic file creation if missing
    - Timestamp tracking
    """

    def __init__(self, pois_file: str | Path = "/data/pois.json"):
        """
        Initialize POI manager.

        Args:
            pois_file: Path to pois.json file
        """
        self.pois_file = Path(pois_file)
        self.lock_file = Path(str(self.pois_file) + ".lock")
        self._pois: dict[str, POI] = {}
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._queue: deque[_QueuedOperation] = deque()
        self._writer_active = False
        self._storage_corrupt = False
        self._load_pois()

    def _ensure_file_exists(self) -> None:
        """Create pois file if it doesn't exist with empty structure.

        Creates parent directories if needed and initializes file with empty JSON structure.
        """
        if not self.pois_file.exists():
            # Create parent directory if needed
            self.pois_file.parent.mkdir(parents=True, exist_ok=True)

            # Write empty POI structure
            initial_data = {"pois": {}, "routes": {}}
            try:
                self._write_json_durable(initial_data)
                logger.info(f"Created initial POI file: {self.pois_file}")
            except OSError as e:
                logger.error(f"Failed to create POI file: {e}")

    def _load_pois(self) -> None:
        """Load POIs from JSON file with file locking.

        Reads POIs from the pois section of the JSON file and converts
        timestamp strings to datetime objects with UTC timezone.
        """
        with self._lock:
            self._ensure_file_exists()

            try:
                data = self._read_json_locked(fail_on_corrupt=False)
            except OSError as e:
                logger.error(f"Failed to load POI file: {e}")
                self._pois = {}
                self._storage_corrupt = False
                return

            # Load POIs from the "pois" section (global POIs)
            pois_section = data.get("pois", {})
            self._pois.clear()

            for poi_id, poi_data in pois_section.items():
                try:
                    self._pois[poi_id] = self._poi_from_json(poi_data)
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
                    logger.warning(f"Failed to load POI {poi_id}: {e}")

            logger.info(f"Loaded {len(self._pois)} POIs from {self.pois_file}")

    def _poi_from_json(self, poi_data: dict[str, Any]) -> POI:
        data = dict(poi_data)
        if isinstance(data.get("created_at"), str):
            created_at = datetime.fromisoformat(data["created_at"])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            data["created_at"] = created_at
        if isinstance(data.get("updated_at"), str):
            updated_at = datetime.fromisoformat(data["updated_at"])
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            data["updated_at"] = updated_at
        return POI(**data)

    def _read_json_locked(self, fail_on_corrupt: bool = True) -> dict[str, Any]:
        lock = FileLock(self.lock_file, timeout=5)
        with lock.acquire(timeout=5):
            return self._read_json_file(fail_on_corrupt=fail_on_corrupt)

    def _read_json_file(self, fail_on_corrupt: bool = True) -> dict[str, Any]:
        try:
            with open(self.pois_file, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self._storage_corrupt = True
            logger.error(f"Failed to load POI file: {e}")
            if fail_on_corrupt:
                raise ValueError("POI storage is corrupt") from e
            return {"pois": {}, "routes": {}}
        except OSError:
            raise
        if not isinstance(data, dict):
            self._storage_corrupt = True
            if fail_on_corrupt:
                raise ValueError("POI storage is corrupt")
            return {"pois": {}, "routes": {}}
        self._storage_corrupt = False
        return data

    def _pois_from_storage(self, data: dict[str, Any]) -> dict[str, POI]:
        pois: dict[str, POI] = {}
        for poi_id, poi_data in data.get("pois", {}).items():
            pois[poi_id] = self._poi_from_json(poi_data)
        return pois

    def _canonical_data(
        self, existing: dict[str, Any], pois: dict[str, POI]
    ) -> dict[str, Any]:
        data = dict(existing)
        data["routes"] = data.get("routes", {})
        data["pois"] = {
            poi_id: self._poi_to_json(poi)
            for poi_id, poi in sorted(pois.items(), key=lambda item: item[0])
        }
        return data

    def _poi_to_json(self, poi: POI) -> dict[str, Any]:
        data = poi.model_dump()
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        if isinstance(data.get("updated_at"), datetime):
            data["updated_at"] = data["updated_at"].isoformat()
        return data

    def _write_json_durable(self, data: dict[str, Any]) -> None:
        self.pois_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.pois_file.with_name(
            f".{self.pois_file.name}-{uuid.uuid4().hex}.tmp"
        )
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        try:
            temp_file.replace(self.pois_file)
            self._fsync_directory(self.pois_file.parent)
        except OSError:
            try:
                temp_file.unlink()
            except OSError:
                pass
            raise

    def _fsync_directory(self, directory: Path) -> None:
        if not hasattr(os, "O_DIRECTORY"):
            return
        try:
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _save_pois(self) -> None:
        """Save POIs to JSON file with file locking and atomic writes.

        Uses atomic write pattern (write to temp file, then rename) to prevent corruption.
        Preserves route data from existing file structure.
        """
        with self._lock:
            lock = FileLock(self.lock_file, timeout=5)
            with lock.acquire(timeout=5):
                existing = self._read_json_file()
                data = self._canonical_data(existing, self._pois)
                self._write_json_durable(data)
            logger.debug(f"Saved {len(self._pois)} POIs to {self.pois_file}")

    def _run_mutation(self, name: str, apply: Callable[[dict[str, POI]], Any]) -> Any:
        operation = _QueuedOperation(name=name, apply=apply)
        with self._condition:
            self._queue.append(operation)
            if self._writer_active:
                while not operation.completed.is_set():
                    self._condition.wait()
                if operation.error:
                    raise operation.error
                return operation.result
            self._writer_active = True

        self._drain_mutations()

        if operation.error:
            raise operation.error
        return operation.result

    def _drain_mutations(self) -> None:
        while True:
            threading.Event().wait(COALESCE_INTERVAL_SECONDS)
            with self._condition:
                operations = list(self._queue)
                self._queue.clear()

            if operations:
                try:
                    with self._lock:
                        lock = FileLock(self.lock_file, timeout=5)
                        with lock.acquire(timeout=5):
                            existing = self._read_json_file()
                            working = self._pois_from_storage(existing)
                            for operation in operations:
                                operation.result = operation.apply(working)
                            data = self._canonical_data(existing, working)
                            self._write_json_durable(data)
                            self._pois = {
                                key: value.model_copy(deep=True)
                                for key, value in working.items()
                            }
                except MUTATION_ERRORS as e:
                    for operation in operations:
                        operation.error = e
                finally:
                    for operation in operations:
                        operation.completed.set()

            with self._condition:
                if not self._queue:
                    self._writer_active = False
                    self._condition.notify_all()
                    return
                self._condition.notify_all()

    def list_pois(
        self, route_id: str | None = None, mission_id: str | None = None
    ) -> list[POI]:
        """
        Get list of POIs, optionally filtered by route or mission.

        Args:
            route_id: Optional route ID to filter by
            mission_id: Optional mission ID to filter by

        Returns:
            List of POI objects
        """
        with self._lock:
            pois = list(self._pois.values())
            if route_id:
                pois = [poi for poi in pois if poi.route_id == route_id]
            if mission_id:
                pois = [poi for poi in pois if poi.mission_id == mission_id]
            return [poi.model_copy(deep=True) for poi in pois]

    def get_poi(self, poi_id: str) -> POI | None:
        """
        Get a specific POI by ID.

        Args:
            poi_id: POI identifier

        Returns:
            POI object or None if not found
        """
        with self._lock:
            poi = self._pois.get(poi_id)
            return poi.model_copy(deep=True) if poi else None

    def find_poi_by_name(self, name: str) -> POI | None:
        """
        Find the first POI matching the provided name (case-insensitive).

        Args:
            name: POI name to search for

        Returns:
            POI object or None if not found
        """
        normalized = name.strip().lower()
        with self._lock:
            for poi in self._pois.values():
                if poi.name.strip().lower() == normalized:
                    return poi.model_copy(deep=True)
        return None

    def find_global_poi_by_name(self, name: str) -> POI | None:
        """
        Find a global (non-scoped) POI by name.

        Args:
            name: POI name to search for

        Returns:
            POI without mission/route scope or None if not found
        """
        normalized = name.strip().lower()
        with self._lock:
            for poi in self._pois.values():
                if (
                    poi.name.strip().lower() == normalized
                    and poi.mission_id is None
                    and poi.route_id is None
                ):
                    return poi.model_copy(deep=True)
        return None

    def delete_scoped_pois_by_names(self, names: set[str]) -> int:
        """
        Delete mission- or route-scoped POIs whose names match.

        Args:
            names: Set of POI names to delete (case-insensitive)

        Returns:
            Number of POIs removed
        """
        normalized = {name.strip().lower() for name in names if name}
        if not normalized:
            return 0

        def apply(pois: dict[str, POI]) -> int:
            removed_ids = []
            for poi_id, poi in list(pois.items()):
                if poi.name.strip().lower() in normalized and (
                    poi.mission_id is not None or poi.route_id is not None
                ):
                    removed_ids.append(poi_id)
                    pois.pop(poi_id, None)
            return len(removed_ids)

        return self._run_mutation("delete_scoped_pois_by_names", apply)

    def create_poi(self, poi_create: POICreate, active_route=None) -> POI:
        """
        Create a new POI.

        Args:
            poi_create: POI creation request data
            active_route: Optional active route to project POI onto

        Returns:
            Created POI object with generated ID

        Raises:
            ValueError: If POI creation fails
        """

        def apply(pois: dict[str, POI]) -> POI:
            poi = self._build_poi(poi_create, pois, active_route)
            pois[poi.id] = poi
            return poi.model_copy(deep=True)

        poi = self._run_mutation("create_poi", apply)
        logger.info(f"Created POI: {poi.id}")
        return poi

    def _build_poi(
        self,
        poi_create: POICreate,
        pois: dict[str, POI],
        active_route=None,
        poi_id: str | None = None,
    ) -> POI:
        slug_source = poi_create.name.lower()
        slug_source = re.sub(r"\s+", "-", slug_source.strip())
        slug_source = re.sub(r"[^a-z0-9\-]+", "", slug_source)
        base_slug = slug_source or f"poi-{uuid.uuid4().hex[:6]}"
        if poi_id:
            candidate_id = poi_id
        elif poi_create.route_id and poi_create.mission_id:
            candidate_id = f"{poi_create.route_id}-{poi_create.mission_id}-{base_slug}"
        elif poi_create.route_id:
            candidate_id = f"{poi_create.route_id}-{base_slug}"
        elif poi_create.mission_id:
            candidate_id = f"{poi_create.mission_id}-{base_slug}"
        else:
            candidate_id = base_slug

        counter = 1
        original_id = candidate_id
        while candidate_id in pois:
            candidate_id = f"{original_id}-{counter}"
            counter += 1

        now = datetime.now(timezone.utc)
        poi = POI(
            id=candidate_id,
            name=poi_create.name,
            latitude=poi_create.latitude,
            longitude=poi_create.longitude,
            icon=poi_create.icon,
            category=poi_create.category,
            description=poi_create.description,
            route_id=poi_create.route_id,
            mission_id=poi_create.mission_id,
            created_at=now,
            updated_at=now,
        )

        # Calculate projection if an active route is provided
        if active_route and active_route.points:
            try:
                from app.services.route_eta_calculator import RouteETACalculator

                calculator = RouteETACalculator(active_route)
                projection = calculator.project_poi_to_route(
                    poi.latitude, poi.longitude
                )

                poi.projected_latitude = projection["projected_lat"]
                poi.projected_longitude = projection["projected_lon"]
                poi.projected_waypoint_index = projection["projected_waypoint_index"]
                poi.projected_route_progress = projection["projected_route_progress"]

                logger.info(f"Projected new POI {candidate_id} onto active route")
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
                logger.warning(
                    f"Failed to project new POI {candidate_id} onto active route: {e}"
                )
        return poi

    def update_poi(self, poi_id: str, poi_update: POIUpdate) -> POI | None:
        """
        Update an existing POI.

        Args:
            poi_id: POI identifier
            poi_update: Update request data

        Returns:
            Updated POI object or None if not found

        Raises:
            ValueError: If update fails
        """

        def apply(pois: dict[str, POI]) -> POI | None:
            if poi_id not in pois:
                return None
            poi = pois[poi_id].model_copy(deep=True)
            update_data = poi_update.model_dump(exclude_unset=True)
            for field_name, value in update_data.items():
                if value is not None:
                    setattr(poi, field_name, value)
            poi.updated_at = datetime.now(timezone.utc)
            pois[poi_id] = poi
            return poi.model_copy(deep=True)

        poi = self._run_mutation("update_poi", apply)
        if poi:
            logger.info(f"Updated POI: {poi_id}")
        else:
            logger.warning(f"Cannot update non-existent POI: {poi_id}")
        return poi

    def delete_poi(self, poi_id: str) -> bool:
        """
        Delete a POI.

        Args:
            poi_id: POI identifier

        Returns:
            True if deleted, False if not found
        """

        def apply(pois: dict[str, POI]) -> bool:
            if poi_id not in pois:
                return False
            del pois[poi_id]
            return True

        deleted = self._run_mutation("delete_poi", apply)
        if deleted:
            logger.info(f"Deleted POI: {poi_id}")
        else:
            logger.warning(f"Cannot delete non-existent POI: {poi_id}")
        return deleted

    def count_pois(self, route_id: str | None = None) -> int:
        """
        Count POIs, optionally by route.

        Args:
            route_id: Optional route ID to filter by

        Returns:
            Number of POIs
        """
        with self._lock:
            if route_id:
                return len(
                    [poi for poi in self._pois.values() if poi.route_id == route_id]
                )
            return len(self._pois)

    def delete_route_pois(self, route_id: str) -> int:
        """
        Delete all POIs associated with a specific route.

        Args:
            route_id: Route identifier

        Returns:
            Number of POIs deleted
        """

        def apply(pois: dict[str, POI]) -> int:
            pois_to_delete = [
                poi_id for poi_id, poi in pois.items() if poi.route_id == route_id
            ]
            for poi_id in pois_to_delete:
                del pois[poi_id]
            return len(pois_to_delete)

        deleted_count = self._run_mutation("delete_route_pois", apply)
        if deleted_count:
            logger.info(f"Deleted {deleted_count} POIs for route: {route_id}")
        return deleted_count

    def delete_mission_pois(self, mission_id: str) -> int:
        """
        Delete all POIs associated with a specific mission.

        Args:
            mission_id: Mission identifier

        Returns:
            Number of POIs deleted
        """

        def apply(pois: dict[str, POI]) -> int:
            pois_to_delete = [
                poi_id for poi_id, poi in pois.items() if poi.mission_id == mission_id
            ]
            for poi_id in pois_to_delete:
                del pois[poi_id]
            return len(pois_to_delete)

        deleted_count = self._run_mutation("delete_mission_pois", apply)
        if deleted_count:
            logger.info(f"Deleted {deleted_count} POIs for mission: {mission_id}")
        return deleted_count

    def delete_mission_pois_by_category(
        self, mission_id: str, categories: set[str]
    ) -> int:
        """Delete mission-scoped POIs that match one of the provided categories.

        Args:
            mission_id: Mission identifier
            categories: Set of category names to match

        Returns:
            Number of POIs deleted
        """
        if not categories:
            return 0

        def apply(pois: dict[str, POI]) -> int:
            to_remove = [
                poi_id
                for poi_id, poi in pois.items()
                if poi.mission_id == mission_id and poi.category in categories
            ]
            for poi_id in to_remove:
                del pois[poi_id]
            return len(to_remove)

        removed = self._run_mutation("delete_mission_pois_by_category", apply)
        if removed:
            logger.info(
                "Deleted %d mission POIs for %s in categories %s",
                removed,
                mission_id,
                sorted(categories),
            )
        return removed

    def delete_mission_pois_by_name_prefixes(
        self, mission_id: str, prefixes: Sequence[str]
    ) -> int:
        """Delete mission POIs whose names start with any of the provided prefixes.

        Args:
            mission_id: Mission identifier
            prefixes: Sequence of name prefixes to match

        Returns:
            Number of POIs deleted
        """
        if not prefixes:
            return 0
        normalized = tuple(prefixes)

        def apply(pois: dict[str, POI]) -> int:
            to_remove = [
                poi_id
                for poi_id, poi in pois.items()
                if poi.mission_id == mission_id
                and any(poi.name.startswith(prefix) for prefix in normalized)
            ]
            for poi_id in to_remove:
                del pois[poi_id]
            return len(to_remove)

        removed = self._run_mutation("delete_mission_pois_by_name_prefixes", apply)
        if removed:
            logger.info(
                "Deleted %d mission POIs for %s with prefixes %s",
                removed,
                mission_id,
                normalized,
            )
        return removed

    def delete_route_mission_pois_with_prefixes(
        self,
        route_id: str,
        prefixes: Sequence[str],
        exclude_mission_id: str | None = None,
    ) -> int:
        """Delete mission POIs on a route whose names start with prefixes.

        Args:
            route_id: Route identifier
            prefixes: Sequence of name prefixes to match
            exclude_mission_id: Optional mission ID to exclude from deletion

        Returns:
            Number of POIs deleted
        """
        if not route_id or not prefixes:
            return 0
        normalized = tuple(prefixes)

        def apply(pois: dict[str, POI]) -> int:
            to_remove = [
                poi_id
                for poi_id, poi in pois.items()
                if poi.route_id == route_id
                and poi.mission_id is not None
                and poi.mission_id != exclude_mission_id
                and any(poi.name.startswith(prefix) for prefix in normalized)
            ]
            for poi_id in to_remove:
                del pois[poi_id]
            return len(to_remove)

        removed = self._run_mutation("delete_route_mission_pois_with_prefixes", apply)
        if removed:
            logger.info(
                "Deleted %d mission POIs on route %s (excluded=%s prefixes=%s)",
                removed,
                route_id,
                exclude_mission_id,
                normalized,
            )
        return removed

    def delete_leg_pois(
        self,
        route_id: str,
        mission_id: str,
        categories: set[str] | None = None,
        prefixes: Sequence[str] | None = None,
    ) -> int:
        """Delete POIs for a specific leg (route_id + mission_id combination).

        Args:
            route_id: Route ID for the leg
            mission_id: Mission ID for the leg
            categories: Optional set of categories to filter by
            prefixes: Optional name prefixes to filter by

        Returns:
            Number of POIs deleted
        """
        if not route_id or not mission_id:
            return 0

        def apply(pois: dict[str, POI]) -> int:
            to_remove = []
            for poi_id, poi in pois.items():
                if poi.route_id == route_id and poi.mission_id == mission_id:
                    if categories and poi.category not in categories:
                        continue
                    if prefixes and not any(
                        poi.name.startswith(prefix) for prefix in prefixes
                    ):
                        continue
                    to_remove.append(poi_id)
            for poi_id in to_remove:
                del pois[poi_id]
            return len(to_remove)

        removed = self._run_mutation("delete_leg_pois", apply)
        if removed:
            logger.info(
                "Deleted %d POIs for leg (route=%s, mission=%s, categories=%s, prefixes=%s)",
                removed,
                route_id,
                mission_id,
                categories,
                prefixes,
            )
        return removed

    def reload_pois(self) -> None:
        """Reload POIs from disk, discarding any unsaved changes.

        Useful for refreshing state when external processes modify the POI file.
        """
        self._load_pois()
        logger.info("Reloaded POIs from disk")

    def calculate_poi_projections(self, route) -> int:
        """
        Calculate route projections for all POIs using a given route.

        Projects each POI onto the route path and stores projection data.

        Args:
            route: ParsedRoute object with waypoints and path information

        Returns:
            Number of POIs that were projected onto the route
        """
        if not route or not route.points:
            return 0

        from app.services.route_eta_calculator import RouteETACalculator

        try:
            calculator = RouteETACalculator(route)
        except (
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as e:
            logger.error(f"Failed to create route ETA calculator: {e}")
            return 0

        def apply(pois: dict[str, POI]) -> int:
            projected_count = 0
            for poi_id, poi in list(pois.items()):
                try:
                    projection = calculator.project_poi_to_route(
                        poi.latitude, poi.longitude
                    )
                    updated = poi.model_copy(deep=True)
                    updated.projected_latitude = projection["projected_lat"]
                    updated.projected_longitude = projection["projected_lon"]
                    updated.projected_waypoint_index = projection[
                        "projected_waypoint_index"
                    ]
                    updated.projected_route_progress = projection[
                        "projected_route_progress"
                    ]
                    pois[poi_id] = updated
                    projected_count += 1
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
                    logger.warning(f"Failed to project POI {poi_id} onto route: {e}")
                    continue
            return projected_count

        projected_count = self._run_mutation("calculate_poi_projections", apply)
        if projected_count > 0:
            logger.info(f"Calculated projections for {projected_count} POIs on route")
        return projected_count

    def clear_poi_projections(self) -> int:
        """
        Clear all route projection data from POIs (typically on route deactivation).

        Returns:
            Number of POIs that had projections cleared
        """

        def apply(pois: dict[str, POI]) -> int:
            cleared_count = 0
            for poi_id, poi in list(pois.items()):
                if (
                    poi.projected_latitude is not None
                    or poi.projected_longitude is not None
                    or poi.projected_waypoint_index is not None
                    or poi.projected_route_progress is not None
                ):
                    updated = poi.model_copy(deep=True)
                    updated.projected_latitude = None
                    updated.projected_longitude = None
                    updated.projected_waypoint_index = None
                    updated.projected_route_progress = None
                    pois[poi_id] = updated
                    cleared_count += 1
            return cleared_count

        cleared_count = self._run_mutation("clear_poi_projections", apply)
        if cleared_count > 0:
            logger.info(f"Cleared projections for {cleared_count} POIs")
        return cleared_count

    def replace_timeline_event_pois(
        self,
        route_id: str,
        mission_id: str,
        generated_pois: Sequence[POICreate],
        route,
    ) -> list[POI]:
        """Atomically replace generated timeline event POIs for one route+mission."""
        if not route_id or not mission_id:
            return []

        def apply(pois: dict[str, POI]) -> list[POI]:
            to_remove = [
                poi_id
                for poi_id, poi in pois.items()
                if (
                    poi.route_id == route_id
                    and poi.mission_id == mission_id
                    and self._is_generated_timeline_event_poi(poi)
                )
            ]
            for poi_id in to_remove:
                del pois[poi_id]

            created: list[POI] = []
            for payload in generated_pois:
                scoped_payload = payload.model_copy(
                    update={"route_id": route_id, "mission_id": mission_id}
                )
                poi = self._build_poi(
                    scoped_payload,
                    pois,
                    active_route=route,
                    poi_id=self._timeline_event_id(
                        route_id,
                        mission_id,
                        scoped_payload.name,
                    ),
                )
                pois[poi.id] = poi
                created.append(poi.model_copy(deep=True))
            return created

        return self._run_mutation("replace_timeline_event_pois", apply)

    def _is_generated_timeline_event_poi(self, poi: POI) -> bool:
        if poi.category != "mission-event":
            return False
        return bool(
            poi.name.startswith(("CommKa", "Ka Coverage", "Ka Transition", "Ka Swap"))
            or poi.name.startswith(("X-Band", "AAR"))
        )

    def _timeline_event_id(self, route_id: str, mission_id: str, name: str) -> str:
        slug = re.sub(r"\s+", "-", name.lower().strip())
        slug = re.sub(r"[^a-z0-9\-]+", "", slug).strip("-")
        return f"{route_id}-{mission_id}-{slug or 'timeline-event'}"
