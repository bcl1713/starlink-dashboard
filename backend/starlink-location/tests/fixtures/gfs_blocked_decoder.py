"""Injected scientific stall uses the production parent-death guard."""

import json
import os
import sys
import time
from pathlib import Path

from app.services.aviation_weather.gfs.decoder_runner import parent_death_guard

parent_death_guard(int(sys.argv[4]))
Path(sys.argv[1]).write_text(json.dumps({"pid": os.getpid(), "pgid": os.getpgrp()}))
while True:
    time.sleep(1)
