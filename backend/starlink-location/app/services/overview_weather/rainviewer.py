"""Initial observed-radar adapter; provider formats never cross the browser API."""

import hashlib
import json
import re
from dataclasses import dataclass

METADATA_URL = "https://api.rainviewer.com/public/weather-maps.json"
TILE_HOST = "https://tilecache.rainviewer.com"
RADAR_PATH = re.compile(r"/v2/radar/[A-Za-z0-9_-]{1,128}")
TILE_PATH = re.compile(
    rf"(?:{RADAR_PATH.pattern}/512/(?P<rz>[2-7])/(?P<rx>0|[1-9][0-9]{{0,2}})/(?P<ry>0|[1-9][0-9]{{0,2}})/2/1_1"
    r"|/v2/coverage/0/512/(?P<cz>[2-7])/(?P<cx>0|[1-9][0-9]{0,2})/(?P<cy>0|[1-9][0-9]{0,2})/0/0_0)\.png"
)


def valid_tile_path(path: str) -> bool:
    match = TILE_PATH.fullmatch(path)
    if not match:
        return False
    prefix = "r" if match["rz"] is not None else "c"
    return all(
        int(match[prefix + axis]) < 2 ** int(match[prefix + "z"]) for axis in ("x", "y")
    )


def observed_frames(body: bytes) -> dict[int, str]:
    payload = json.loads(body)
    if (
        not isinstance(payload, dict)
        or len(payload) > 16
        or payload.get("host") != TILE_HOST
    ):
        raise ValueError("Invalid weather metadata")
    radar = payload.get("radar")
    if not isinstance(radar, dict) or len(radar) > 8:
        raise ValueError("Invalid radar metadata")
    past = radar.get("past")
    if not isinstance(past, list) or len(past) > 32:
        raise ValueError("Invalid observed frame list")
    frames = {}
    for entry in past:
        if not isinstance(entry, dict) or len(entry) > 4:
            raise ValueError("Invalid observed frame")
        timestamp, path = entry.get("time"), entry.get("path")
        if (
            type(timestamp) is not int
            or timestamp < 0
            or not isinstance(path, str)
            or not RADAR_PATH.fullmatch(path)
            or (timestamp in frames and frames[timestamp] != path)
        ):
            raise ValueError("Invalid observed frame identity")
        frames[timestamp] = path
    return frames


@dataclass(frozen=True)
class RainViewerAdapter:
    source: str = "rainviewer"
    provenance: str = "RainViewer observed radar"
    max_zoom: int = 7

    def normalized(self) -> dict:
        machine = {
            "source": self.source,
            "product": "observed-precipitation",
            "tile_schema": "xyz-rgba-pair-v1",
            "coverage_encoding": "absence-rgba-v1",
            "zoom": 2,
            "max_zoom": self.max_zoom,
            "tile_size": 512,
        }
        identity = hashlib.sha256(
            json.dumps(machine, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return dict(
            **machine,
            product_id=identity,
            provenance=self.provenance,
            attribution={"label": "RainViewer", "url": "https://www.rainviewer.com/"},
        )

    metadata_url = METADATA_URL
    observed_frames = staticmethod(observed_frames)

    @staticmethod
    def tile_url(kind: str, path: str | None, z: int, x: int, y: int) -> str:
        suffix = (
            f"{path}/512/{z}/{x}/{y}/2/1_1.png"
            if kind == "radar"
            else f"/v2/coverage/0/512/{z}/{x}/{y}/0/0_0.png"
        )
        return TILE_HOST + suffix
