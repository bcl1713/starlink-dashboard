"""POI manager for loading, saving, and managing points of interest."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from filelock import FileLock

from app.models.poi import POI, POICreate, POIUpdate

logger = logging.getLogger(__name__)


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
                with open(self.pois_file, "w") as f:
                    json.dump(initial_data, f, indent=2)
                logger.info(f"Created initial POI file: {self.pois_file}")
            except IOError as e:
                logger.error(f"Failed to create POI file: {e}")

    def _load_pois(self) -> None:
        """Load POIs from JSON file with file locking.

        Reads POIs from the pois section of the JSON file and converts
        timestamp strings to datetime objects with UTC timezone.
        """
        self._ensure_file_exists()

        lock = FileLock(self.lock_file, timeout=5)
        try:
            with lock.acquire(timeout=5):
                with open(self.pois_file, "r") as f:
                    data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load POI file: {e}")
            self._pois = {}
            return
        except Exception as e:
            logger.error(f"Failed to acquire lock for reading POI file: {e}")
            self._pois = {}
            return

        # Load POIs from the "pois" section (global POIs)
        pois_section = data.get("pois", {})
        self._pois.clear()

        for poi_id, poi_data in pois_section.items():
            try:
                # Ensure timestamps are datetime objects
                if isinstance(poi_data.get("created_at"), str):
                    created_at = datetime.fromisoformat(poi_data["created_at"])
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    poi_data["created_at"] = created_at
                if isinstance(poi_data.get("updated_at"), str):
                    updated_at = datetime.fromisoformat(poi_data["updated_at"])
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    poi_data["updated_at"] = updated_at

                poi = POI(**poi_data)
                self._pois[poi_id] = poi
            except Exception as e:
                logger.warning(f"Failed to load POI {poi_id}: {e}")

        logger.info(f"Loaded {len(self._pois)} POIs from {self.pois_file}")

    def _save_pois(self) -> None:
        """Save POIs to JSON file with file locking and atomic writes.

        Uses atomic write pattern (write to temp file, then rename) to prevent corruption.
        Preserves route data from existing file structure.
        """
        lock = FileLock(self.lock_file, timeout=5)
        try:
            with lock.acquire(timeout=5):
                try:
                    # Load existing file to preserve route data
                    with open(self.pois_file, "r") as f:
                        data = json.load(f)
                except (IOError, json.JSONDecodeError):
                    data = {"pois": {}, "routes": {}}

                # Update pois section
                pois_section = {}
                for poi_id, poi in self._pois.items():
                    poi_dict = poi.model_dump()
                    # Convert datetime to ISO format for JSON serialization
                    if isinstance(poi_dict.get("created_at"), datetime):
                        poi_dict["created_at"] = poi_dict["created_at"].isoformat()
                    if isinstance(poi_dict.get("updated_at"), datetime):
                        poi_dict["updated_at"] = poi_dict["updated_at"].isoformat()
                    pois_section[poi_id] = poi_dict

                data["pois"] = pois_section

                # Atomic write pattern: write to temp file, then atomic rename
                temp_file = self.pois_file.with_suffix(".tmp")
                try:
                    with open(temp_file, "w") as f:
                        json.dump(data, f, indent=2)
                    # Atomic rename (platform-specific but reliable on both Unix and Windows)
                    temp_file.replace(self.pois_file)
                    logger.debug(f"Saved {len(self._pois)} POIs to {self.pois_file}")
                except IOError as e:
                    logger.error(f"Failed to save POI file: {e}")
                    # Clean up temp file if it exists
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Failed to acquire lock for writing POI file: {e}")

    def list_pois(
        self, route_id: Optional[str] = None, mission_id: Optional[str] = None
    ) -> list[POI]:
        """
        Get list of POIs, optionally filtered by route or mission.

        Args:
            route_id: Optional route ID to filter by
            mission_id: Optional mission ID to filter by

        Returns:
            List of POI objects
        """
        pois = list(self._pois.values())
        if route_id:
            pois = [poi for poi in pois if poi.route_id == route_id]
        if mission_id:
            pois = [poi for poi in pois if poi.mission_id == mission_id]
        return pois

    def get_poi(self, poi_id: str) -> Optional[POI]:
        """
        Get a specific POI by ID.

        Args:
            poi_id: POI identifier

        Returns:
            POI object or None if not found
        """
        return self._pois.get(poi_id)

    def find_poi_by_name(self, name: str) -> Optional[POI]:
        """
        Find the first POI matching the provided name (case-insensitive).

        Args:
            name: POI name to search for

        Returns:
            POI object or None if not found
        """
        normalized = name.strip().lower()
        for poi in self._pois.values():
            if poi.name.strip().lower() == normalized:
                return poi
        return None

    def find_global_poi_by_name(self, name: str) -> Optional[POI]:
        """
        Find a global (non-scoped) POI by name.

        Args:
            name: POI name to search for

        Returns:
            POI without mission/route scope or None if not found
        """
        normalized = name.strip().lower()
        for poi in self._pois.values():
            if (
                poi.name.strip().lower() == normalized
                and poi.mission_id is None
                and poi.route_id is None
            ):
                return poi
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

        removed_ids: list[str] = []
        for poi_id, poi in list(self._pois.items()):
            if poi.name.strip().lower() in normalized and (
                poi.mission_id is not None or poi.route_id is not None
            ):
                removed_ids.append(poi_id)
                self._pois.pop(poi_id, None)

        if removed_ids:
            self._save_pois()
        return len(removed_ids)

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
        slug_source = poi_create.name.lower()
        slug_source = re.sub(r"\s+", "-", slug_source.strip())
        slug_source = re.sub(r"[^a-z0-9\-]+", "", slug_source)
        base_slug = slug_source or f"poi-{uuid.uuid4().hex[:6]}"
        if poi_create.route_id:
            poi_id = f"{poi_create.route_id}-{base_slug}"
        elif poi_create.mission_id:
            poi_id = f"{poi_create.mission_id}-{base_slug}"
        else:
            poi_id = base_slug

        # Ensure unique ID
        counter = 1
        original_id = poi_id
        while poi_id in self._pois:
            poi_id = f"{original_id}-{counter}"
            counter += 1

        now = datetime.now(timezone.utc)
        poi = POI(
            id=poi_id,
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

                logger.info(f"Projected new POI {poi_id} onto active route")
            except Exception as e:
                logger.warning(
                    f"Failed to project new POI {poi_id} onto active route: {e}"
                )

        self._pois[poi_id] = poi
        self._save_pois()

        logger.info(f"Created POI: {poi_id}")
        return poi

    def update_poi(self, poi_id: str, poi_update: POIUpdate) -> Optional[POI]:
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
        if poi_id not in self._pois:
            logger.warning(f"Cannot update non-existent POI: {poi_id}")
            return None

        poi = self._pois[poi_id]

        # Update fields if provided
        update_data = poi_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(poi, field, value)

        # Update timestamp
        poi.updated_at = datetime.now(timezone.utc)

        self._pois[poi_id] = poi
        self._save_pois()

        logger.info(f"Updated POI: {poi_id}")
        return poi

    def delete_poi(self, poi_id: str) -> bool:
        """
        Delete a POI.

        Args:
            poi_id: POI identifier

        Returns:
            True if deleted, False if not found
        """
        if poi_id not in self._pois:
            logger.warning(f"Cannot delete non-existent POI: {poi_id}")
            return False

        del self._pois[poi_id]
        self._save_pois()

        logger.info(f"Deleted POI: {poi_id}")
        return True

    def count_pois(self, route_id: Optional[str] = None) -> int:
        """
        Count POIs, optionally by route.

        Args:
            route_id: Optional route ID to filter by

        Returns:
            Number of POIs
        """
        if route_id:
            return len([poi for poi in self._pois.values() if poi.route_id == route_id])
        return len(self._pois)

    def delete_route_pois(self, route_id: str) -> int:
        """
        Delete all POIs associated with a specific route.

        Args:
            route_id: Route identifier

        Returns:
            Number of POIs deleted
        """
        pois_to_delete = [
            poi_id for poi_id, poi in self._pois.items() if poi.route_id == route_id
        ]

        for poi_id in pois_to_delete:
            del self._pois[poi_id]

        if pois_to_delete:
            self._save_pois()
            logger.info(f"Deleted {len(pois_to_delete)} POIs for route: {route_id}")

        return len(pois_to_delete)

    def delete_mission_pois(self, mission_id: str) -> int:
        """
        Delete all POIs associated with a specific mission.

        Args:
            mission_id: Mission identifier

        Returns:
            Number of POIs deleted
        """
        pois_to_delete = [
            poi_id for poi_id, poi in self._pois.items() if poi.mission_id == mission_id
        ]

        for poi_id in pois_to_delete:
            del self._pois[poi_id]

        if pois_to_delete:
            self._save_pois()
            logger.info(f"Deleted {len(pois_to_delete)} POIs for mission: {mission_id}")

        return len(pois_to_delete)

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
        to_remove = [
            poi_id
            for poi_id, poi in self._pois.items()
            if poi.mission_id == mission_id and poi.category in categories
        ]

        for poi_id in to_remove:
            del self._pois[poi_id]

        if to_remove:
            self._save_pois()
            logger.info(
                "Deleted %d mission POIs for %s in categories %s",
                len(to_remove),
                mission_id,
                sorted(categories),
            )

        return len(to_remove)

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
        to_remove = [
            poi_id
            for poi_id, poi in self._pois.items()
            if poi.mission_id == mission_id
            and any(poi.name.startswith(prefix) for prefix in normalized)
        ]
        for poi_id in to_remove:
            del self._pois[poi_id]
        if to_remove:
            self._save_pois()
            logger.info(
                "Deleted %d mission POIs for %s with prefixes %s",
                len(to_remove),
                mission_id,
                normalized,
            )
        return len(to_remove)

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
        to_remove = [
            poi_id
            for poi_id, poi in self._pois.items()
            if poi.route_id == route_id
            and poi.mission_id is not None
            and poi.mission_id != exclude_mission_id
            and any(poi.name.startswith(prefix) for prefix in normalized)
        ]
        for poi_id in to_remove:
            del self._pois[poi_id]
        if to_remove:
            self._save_pois()
            logger.info(
                "Deleted %d mission POIs on route %s (excluded=%s prefixes=%s)",
                len(to_remove),
                route_id,
                exclude_mission_id,
                normalized,
            )
        return len(to_remove)

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

        to_remove = []
        for poi_id, poi in self._pois.items():
            if poi.route_id == route_id and poi.mission_id == mission_id:
                # Check category filter
                if categories and poi.category not in categories:
                    continue
                # Check prefix filter
                if prefixes and not any(
                    poi.name.startswith(prefix) for prefix in prefixes
                ):
                    continue
                to_remove.append(poi_id)

        for poi_id in to_remove:
            del self._pois[poi_id]

        if to_remove:
            self._save_pois()
            logger.info(
                "Deleted %d POIs for leg (route=%s, mission=%s, categories=%s, prefixes=%s)",
                len(to_remove),
                route_id,
                mission_id,
                categories,
                prefixes,
            )
        return len(to_remove)

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
        except Exception as e:
            logger.error(f"Failed to create route ETA calculator: {e}")
            return 0

        projected_count = 0

        for poi_id, poi in list(self._pois.items()):
            try:
                projection = calculator.project_poi_to_route(
                    poi.latitude, poi.longitude
                )

                # Update POI with projection data
                poi.projected_latitude = projection["projected_lat"]
                poi.projected_longitude = projection["projected_lon"]
                poi.projected_waypoint_index = projection["projected_waypoint_index"]
                poi.projected_route_progress = projection["projected_route_progress"]

                # Ensure the POI object is updated in the dict
                self._pois[poi_id] = poi

                projected_count += 1
            except Exception as e:
                logger.warning(f"Failed to project POI {poi_id} onto route: {e}")
                continue

        # Save POIs with projection data
        if projected_count > 0:
            self._save_pois()
            logger.info(f"Calculated projections for {projected_count} POIs on route")

        return projected_count

    def clear_poi_projections(self) -> int:
        """
        Clear all route projection data from POIs (typically on route deactivation).

        Returns:
            Number of POIs that had projections cleared
        """
        cleared_count = 0

        for poi_id, poi in self._pois.items():
            if (
                poi.projected_latitude is not None
                or poi.projected_longitude is not None
                or poi.projected_waypoint_index is not None
                or poi.projected_route_progress is not None
            ):
                poi.projected_latitude = None
                poi.projected_longitude = None
                poi.projected_waypoint_index = None
                poi.projected_route_progress = None
                cleared_count += 1

        # Save POIs with cleared projections
        if cleared_count > 0:
            self._save_pois()
            logger.info(f"Cleared projections for {cleared_count} POIs")

        return cleared_count
