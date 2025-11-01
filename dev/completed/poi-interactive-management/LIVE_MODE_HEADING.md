# Live Mode Heading Calculation

## Problem

In **simulation mode**, heading is calculated by the route classes (`CircularRoute`, `StraightRoute`) based on the predefined path. However, in **live mode**, we'll receive GPS coordinates from the actual Starlink terminal, which may not include heading data.

## Solution

The heading must be calculated from **successive position updates** using the bearing formula between two GPS coordinates.

## Implementation

### 1. HeadingTracker Class

Located at: `app/services/heading_tracker.py`

```python
from app.services.heading_tracker import HeadingTracker

# Initialize tracker
tracker = HeadingTracker(
    min_distance_meters=10.0,  # Minimum movement to update heading
    max_age_seconds=30.0        # Discard stale positions
)

# Update with each new GPS position
heading = tracker.update(
    latitude=41.612,
    longitude=-74.006,
    timestamp=datetime.now()
)
```

### 2. How It Works

**Bearing Calculation Formula:**
```
θ = atan2(sin(Δλ) * cos(φ2), cos(φ1) * sin(φ2) - sin(φ1) * cos(φ2) * cos(Δλ))
```

Where:
- φ1, λ1 = previous position (latitude, longitude)
- φ2, λ2 = current position (latitude, longitude)
- Δλ = λ2 - λ1

**Smart Filtering:**
- Only recalculates heading when moved ≥10 meters (prevents GPS jitter when stationary)
- Discards positions older than 30 seconds (prevents stale data)
- Returns last known heading if insufficient movement

### 3. Integration Example (Future Live Mode)

```python
class LiveCoordinator:
    """Coordinator for live Starlink data acquisition."""

    def __init__(self):
        self.heading_tracker = HeadingTracker(
            min_distance_meters=10.0,
            max_age_seconds=30.0
        )

    def fetch_telemetry(self) -> TelemetryData:
        """Fetch telemetry from live Starlink terminal."""

        # Get position from Starlink API (e.g., grpc call to 192.168.100.1:9200)
        starlink_data = self._query_starlink_api()

        # Extract GPS coordinates
        latitude = starlink_data.get('latitude')
        longitude = starlink_data.get('longitude')
        altitude = starlink_data.get('altitude')

        # Calculate heading from movement
        heading = self.heading_tracker.update(
            latitude=latitude,
            longitude=longitude,
            timestamp=datetime.now()
        )

        # Build position data with calculated heading
        position = PositionData(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            speed=self._calculate_speed(),  # Also from successive positions
            heading=heading  # ✅ Calculated from movement!
        )

        return TelemetryData(
            timestamp=datetime.now(),
            position=position,
            network=self._fetch_network_data(starlink_data),
            obstruction=self._fetch_obstruction_data(starlink_data),
            environmental=self._fetch_environmental_data(starlink_data)
        )
```

## Key Benefits

1. **Accurate Direction**: Heading reflects actual direction of travel, not GPS compass (which can be inaccurate when stationary)
2. **Handles Stationary Periods**: Won't jitter when vehicle is stopped
3. **Graceful Degradation**: Returns last known heading if insufficient data
4. **Works with Any GPS Source**: Only needs lat/lon coordinates, no special hardware

## Testing

The `calculate_bearing()` function in `app/simulation/route.py` can be tested independently:

```python
from app.simulation.route import calculate_bearing

# Moving east
heading = calculate_bearing(41.5, -74.0, 41.5, -73.9)  # ≈ 90° (East)

# Moving north
heading = calculate_bearing(41.5, -74.0, 41.6, -74.0)  # ≈ 0° (North)

# Moving northeast
heading = calculate_bearing(41.5, -74.0, 41.6, -73.9)  # ≈ 45° (Northeast)
```

## Current Status

- ✅ **Simulation Mode**: Uses route-based heading calculation (working correctly)
- ✅ **Utility Functions**: `calculate_bearing()` implemented and tested
- ✅ **HeadingTracker**: Ready for live mode integration
- ⏳ **Live Mode Coordinator**: To be implemented in future phase

## Related Files

- `app/simulation/route.py` - Contains `calculate_bearing()` function
- `app/services/heading_tracker.py` - HeadingTracker class for live mode
- `app/simulation/position.py` - Current simulation mode position calculator
- `app/simulation/coordinator.py` - Current simulation coordinator
