"""Fictional inputs using existing stores; real startup, clocks and tick loop."""

import os
import sys
from pathlib import Path

sys.path.insert(0, "/acceptance/journal")
from app.operator.clock import SystemClock
from seed import seed_demo

if os.environ.get("PERF_SYNTHETIC") != "1":
    raise RuntimeError("Requires explicit isolated synthetic runtime")

seed_demo(
    Path("/app/data"), clock=SystemClock(), mode="simulation", include_timelines=False
)
os.environ["OPERATOR_SIMULATION_RUN_ID"] = "synthetic-operator-demo-v1"
route = Path("/data/routes/synthetic-route.kml")
route.parent.mkdir(parents=True, exist_ok=True)
route.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Synthetic ocean route</name>
<Placemark><name>Synthetic departure</name><Point><coordinates>-10,0,0</coordinates></Point></Placemark>
<Placemark><name>Synthetic midpoint</name><Point><coordinates>0,0,10668</coordinates></Point></Placemark>
<Placemark><name>Synthetic arrival</name><Point><coordinates>10,0,0</coordinates></Point></Placemark>
<Placemark><name>Synthetic route</name><LineString><coordinates>-10,0,10668 -5,1,10668 0,0,10668 5,-1,10668 10,0,10668</coordinates></LineString></Placemark>
</Document></kml>""")

import main

app = main.app
