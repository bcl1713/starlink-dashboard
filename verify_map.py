
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Add project root to path
sys.path.append('/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location')

from app.mission.exporter import _generate_route_map, set_route_manager, set_poi_manager
from app.mission.models import Mission, MissionTimeline, TransportConfig
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager

def verify_map_generation():
    print("Verifying map generation...")
    
    # Mock managers
    route_manager = MagicMock(spec=RouteManager)
    poi_manager = MagicMock(spec=POIManager)
    
    # Mock route
    mock_route = MagicMock()
    mock_route.points = [
        MagicMock(latitude=30, longitude=-90),
        MagicMock(latitude=35, longitude=-80),
        MagicMock(latitude=40, longitude=-70)
    ]
    route_manager.get_route.return_value = mock_route
    
    # Mock POIs
    mock_poi = MagicMock()
    mock_poi.latitude = 32
    mock_poi.longitude = -85
    mock_poi.name = "Test POI"
    poi_manager.list_pois.return_value = [mock_poi]
    
    # Set managers
    set_route_manager(route_manager)
    set_poi_manager(poi_manager)
    
    # Mock Mission
    mission = Mission(
        id="test-mission",
        name="Test Mission",
        route_id="test-route",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            aar_windows=[],
            x_transitions=[]
        )
    )
    
    # Mock Timeline
    timeline = MissionTimeline(
        segments=[]
    )
    
    try:
        image_bytes = _generate_route_map(timeline, mission)
        if image_bytes and len(image_bytes) > 0:
            print("SUCCESS: Map generated successfully.")
            # Save to file for manual inspection if needed
            with open("test_map.png", "wb") as f:
                f.write(image_bytes)
            print("Map saved to test_map.png")
        else:
            print("FAILURE: Map generation returned empty bytes.")
    except Exception as e:
        print(f"FAILURE: Map generation raised exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_map_generation()
