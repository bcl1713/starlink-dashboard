#!/usr/bin/env python3
"""Quick test script to trigger PDF export and see bounds calculation."""

import sys
import os

# Change to app directory
os.chdir('/app')
sys.path.insert(0, '/app')

from app.services.route_manager import RouteManager
from app.mission.timeline import build_timeline_segments, assemble_mission_timeline
from app.mission.exporter import generate_pdf_export

def test_bounds():
    """Test bounds calculation for IDL-crossing route."""

    # Initialize route manager
    route_manager = RouteManager(routes_dir="/data/routes")

    # Force reload of all routes
    route_manager.reload_all_routes()

    # List available routes
    routes = route_manager.list_routes()
    print(f"Available routes: {list(routes.keys())}\n")

    # Get the Leg 6 route (IDL-crossing)
    route = route_manager.get_route("Leg 6 Rev 6")
    if not route:
        print("ERROR: Route 'Leg 6 Rev 6' not found!")
        return

    print(f"Found route!")
    print(f"Route fields: {dir(route)[:10]}")  # First 10 to keep it short

    # Build timeline
    segments = build_timeline_segments(route=route, transports=[])
    timeline = assemble_mission_timeline(segments, transports=[])

    print(f"\nTimeline built with {len(timeline.segments)} segments")

    # Generate PDF export - this will trigger bounds calculation
    print("\n=== Triggering PDF export (bounds calculation will be logged) ===\n")
    pdf_bytes = generate_pdf_export(timeline, mission=None)

    print(f"\n=== PDF export complete ({len(pdf_bytes)} bytes) ===")

if __name__ == "__main__":
    test_bounds()
