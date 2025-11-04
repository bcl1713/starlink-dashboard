"""POI manager for loading, saving, and managing points of interest."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

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
        """Create pois file if it doesn't exist with empty structure."""
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
        """Load POIs from JSON file with file locking."""
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
                    poi_data["created_at"] = datetime.fromisoformat(poi_data["created_at"])
                if isinstance(poi_data.get("updated_at"), str):
                    poi_data["updated_at"] = datetime.fromisoformat(poi_data["updated_at"])

                poi = POI(**poi_data)
                self._pois[poi_id] = poi
            except Exception as e:
                logger.warning(f"Failed to load POI {poi_id}: {e}")

        logger.info(f"Loaded {len(self._pois)} POIs from {self.pois_file}")

    def _save_pois(self) -> None:
        """Save POIs to JSON file with file locking and atomic writes."""
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
                temp_file = self.pois_file.with_suffix('.tmp')
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

    def list_pois(self, route_id: Optional[str] = None) -> list[POI]:
        """
        Get list of POIs, optionally filtered by route.

        Args:
            route_id: Optional route ID to filter by

        Returns:
            List of POI objects
        """
        if route_id:
            return [poi for poi in self._pois.values() if poi.route_id == route_id]
        return list(self._pois.values())

    def get_poi(self, poi_id: str) -> Optional[POI]:
        """
        Get a specific POI by ID.

        Args:
            poi_id: POI identifier

        Returns:
            POI object or None if not found
        """
        return self._pois.get(poi_id)

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
        # Generate unique ID if not provided
        poi_id = poi_create.route_id + "-" + poi_create.name.lower().replace(" ", "-") if poi_create.route_id else poi_create.name.lower().replace(" ", "-")

        # Ensure unique ID
        counter = 1
        original_id = poi_id
        while poi_id in self._pois:
            poi_id = f"{original_id}-{counter}"
            counter += 1

        now = datetime.utcnow()
        poi = POI(
            id=poi_id,
            name=poi_create.name,
            latitude=poi_create.latitude,
            longitude=poi_create.longitude,
            icon=poi_create.icon,
            category=poi_create.category,
            description=poi_create.description,
            route_id=poi_create.route_id,
            created_at=now,
            updated_at=now,
        )

        # Calculate projection if an active route is provided
        if active_route and active_route.points:
            try:
                from app.services.route_eta_calculator import RouteETACalculator
                calculator = RouteETACalculator(active_route)
                projection = calculator.project_poi_to_route(poi.latitude, poi.longitude)

                poi.projected_latitude = projection["projected_lat"]
                poi.projected_longitude = projection["projected_lon"]
                poi.projected_waypoint_index = projection["projected_waypoint_index"]
                poi.projected_route_progress = projection["projected_route_progress"]

                logger.info(f"Projected new POI {poi_id} onto active route")
            except Exception as e:
                logger.warning(f"Failed to project new POI {poi_id} onto active route: {e}")

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
        poi.updated_at = datetime.utcnow()

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
        pois_to_delete = [poi_id for poi_id, poi in self._pois.items() if poi.route_id == route_id]

        for poi_id in pois_to_delete:
            del self._pois[poi_id]

        if pois_to_delete:
            self._save_pois()
            logger.info(f"Deleted {len(pois_to_delete)} POIs for route: {route_id}")

        return len(pois_to_delete)

    def reload_pois(self) -> None:
        """Reload POIs from disk, discarding any unsaved changes."""
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
                projection = calculator.project_poi_to_route(poi.latitude, poi.longitude)

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
