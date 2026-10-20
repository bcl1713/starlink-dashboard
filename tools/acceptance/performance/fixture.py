"""Fictional inputs using existing stores; real startup, clocks and tick loop."""

import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, "/acceptance/journal")
from app.mission import storage
from app.operator.clock import SystemClock
from app.operator.models import Actor
from app.operator.references import MissionReferences
from app.operator.service import OperatorService
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from scenario import make_demo

if os.environ.get("PERF_SYNTHETIC") != "1":
    raise RuntimeError("Requires explicit isolated synthetic runtime")

clock = SystemClock()
demo = make_demo(clock)
storage.MISSIONS_DIR = Path("/app/data/missions")
for mission in demo["missions"]:
    storage.save_mission_v2(mission)
settings = OperatorSettings(
    root=Path("/app/data/operator"),
    source_mode="simulation",
    simulation_run_id="default",
    mission_journal=True,
)
store = OperatorStore.open(settings, initialize=True, clock=clock)
try:
    service = OperatorService(
        store,
        clock=clock,
        actor=Actor(backend="synthetic performance seed"),
        references=MissionReferences(),
    )
    epoch = str(store.health().api_epoch)
    for index, command in enumerate(demo["commands"]):
        service.execute(
            command, key=str(uuid5(NAMESPACE_URL, f"perf390-v1/{index}")), epoch=epoch
        )
finally:
    store.close()
os.environ["OPERATOR_SIMULATION_RUN_ID"] = "synthetic-operator-demo-v1"
route = Path("/data/routes/synthetic-route.kml")
route.parent.mkdir(parents=True, exist_ok=True)
start = clock.now()
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
