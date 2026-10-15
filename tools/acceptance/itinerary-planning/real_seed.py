"""Create only the four authorized diagnostic satellites in the owned fixture."""

import argparse
import json
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--origin", required=True)
parser.add_argument("--input-root", required=True)
args = parser.parse_args()
for ordinal, longitude in enumerate([-180, -90, 0, 90], 1):
    payload = dict(
        satellite_id=f"TEST-ONLY-X-{ordinal}",
        transport="X",
        longitude=longitude,
        slot="AUTHORIZED FAKE DIAGNOSTIC ONLY; NOT OPERATIONAL",
        color="#FFA500",
    )
    request = Request(
        args.origin + "/api/satellites",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        assert response.status in (200, 201)
