"""Fictional inputs using existing stores; real startup, clocks and tick loop."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/acceptance/journal")
from app.operator.clock import SystemClock
from seed import seed_demo

if os.environ.get("PERF_SYNTHETIC") != "1":
    raise RuntimeError("Requires explicit isolated synthetic runtime")

seed = seed_demo(
    Path("/app/data"), clock=SystemClock(), mode="simulation", include_timelines=False
)
os.environ["OPERATOR_SIMULATION_RUN_ID"] = "synthetic-operator-demo-v1"
route = Path("/data/routes/synthetic-route.kml")
route.parent.mkdir(parents=True, exist_ok=True)
start = datetime.fromisoformat(seed["started_at"])
departure = start.strftime("%Y-%m-%d %H:%M:%S")
midpoint = (start + timedelta(hours=1, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
arrival = (start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
route.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Synthetic ocean route</name>
<Placemark><name>Synthetic departure</name><description>Time Over Waypoint: {departure}Z</description><Point><coordinates>-10,0,0</coordinates></Point></Placemark>
<Placemark><name>Synthetic midpoint</name><description>Time Over Waypoint: {midpoint}Z</description><Point><coordinates>0,0,10668</coordinates></Point></Placemark>
<Placemark><name>Synthetic arrival</name><description>Time Over Waypoint: {arrival}Z</description><Point><coordinates>10,0,0</coordinates></Point></Placemark>
<Placemark><name>Synthetic route</name><LineString><coordinates>-10,0,10668 -5,1,10668 0,0,10668 5,-1,10668 10,0,10668</coordinates></LineString></Placemark>
</Document></kml>""")

import main

app = main.app
