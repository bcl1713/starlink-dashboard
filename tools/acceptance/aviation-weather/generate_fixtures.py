"""Source-shaped bulletin controls consumed by the real production normalizer."""

import copy
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def generate(root, now=None):
    root.mkdir(parents=True, exist_ok=True)
    now = int(time.time() * 1000) if now is None else now

    def utc(offset):
        return (
            datetime.fromtimestamp((now + offset) / 1000, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    stations = [
        ("KJFK", 40.64, -73.78, "BKN", "700"),
        ("EGLL", 51.47, -0.45, "OVC", "300"),
        ("PHNL", 21.32, -157.92, "CLR", None),
        ("RJTT", 35.55, 139.78, "FEW", "3000"),
    ]
    metars = []
    tafs = []
    for name, lat, lon, sky, ceiling in stations:
        condition = (
            f'<sky_condition sky_cover="{sky}"'
            + (f' cloud_base_ft_agl="{ceiling}"' if ceiling else "")
            + "/>"
        )
        position = f"<station_id>{name}</station_id><latitude>{lat}</latitude><longitude>{lon}</longitude>"
        metars.append(
            f"<METAR><raw_text>METAR {name} 000000Z 24012G20KT 4SM {sky}007 15/10 A2992</raw_text>{position}<observation_time>{utc(-600000)}</observation_time><metar_type>METAR</metar_type><wind_dir_degrees>240</wind_dir_degrees><wind_speed_kt>12</wind_speed_kt><wind_gust_kt>20</wind_gust_kt><visibility_statute_mi>4</visibility_statute_mi><temp_c>15</temp_c><dewpoint_c>10</dewpoint_c><altim_in_hg>29.92</altim_in_hg>{condition}</METAR>"
        )
        tafs.append(
            f'<TAF><raw_text>TAF {name} 000000Z 0000/0000 24012KT P6SM SCT030 TEMPO 0000/0000 2SM BKN007</raw_text>{position}<issue_time>{utc(-300000)}</issue_time><valid_time_from>{utc(-600000)}</valid_time_from><valid_time_to>{utc(7200000)}</valid_time_to><forecast><fcst_time_from>{utc(-600000)}</fcst_time_from><fcst_time_to>{utc(7200000)}</fcst_time_to><wind_dir_degrees>240</wind_dir_degrees><wind_speed_kt>12</wind_speed_kt><visibility_statute_mi>6+</visibility_statute_mi><sky_condition sky_cover="SCT" cloud_base_ft_agl="3000"/></forecast><forecast><fcst_time_from>{utc(600000)}</fcst_time_from><fcst_time_to>{utc(3600000)}</fcst_time_to><change_indicator>TEMPO</change_indicator><visibility_statute_mi>2</visibility_statute_mi><sky_condition sky_cover="BKN" cloud_base_ft_agl="700"/></forecast></TAF>'
        )
    for product, records in [("metar", metars), ("taf", tafs)]:
        body = (
            f'<response><data_source name="{product}"/><errors/><data num_results="{len(records)}">'
            + "".join(records)
            + "</data></response>"
        )
        (root / ("metars.xml.gz" if product == "metar" else "tafs.xml.gz")).write_bytes(
            gzip.compress(body.encode())
        )

    def feature(series, rings, hazard="TURB", raw=None):
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": rings},
            "properties": {
                "icaoId": "KZNY",
                "firId": "KZNY",
                "seriesId": series,
                "hazard": hazard,
                "qualifier": "SEV",
                "validTimeFrom": utc(-600000),
                "validTimeTo": utc(7200000),
                "rawSigmet": raw or f"KZNY SIGMET {series} SEV {hazard} FL180/FL340",
            },
        }

    features = [
        feature(
            "A1",
            [
                [[-80, 34], [-67, 34], [-67, 46], [-80, 46], [-80, 34]],
                [[-76, 38], [-72, 38], [-72, 42], [-76, 42], [-76, 38]],
            ],
        ),
        feature(
            "B1", [[[170, 35], [-170, 35], [-170, 48], [170, 48], [170, 35]]], "ICE"
        ),
        feature(
            "C1",
            [[[0, 0], [0, 0], [0, 0], [0, 0]]],
            raw="KZNY SIGMET C1 SEV TURB FL180/FL340",
        ),
    ]
    (root / "sigmets.json").write_text(
        json.dumps({"type": "FeatureCollection", "features": features})
    )
    # Separate route controls preserve the original hole/seam station suite.
    route = [
        feature(
            f"R{i}",
            [
                [
                    [-80 + i, 33],
                    [-71 + i, 33],
                    [-71 + i, 38],
                    [-80 + i, 38],
                    [-80 + i, 33],
                ]
            ],
        )
        for i in range(1, 5)
    ]
    route.append(features[1])  # located nonintersecting seam control
    route.append(features[2])  # explicitly unlocated report, never a false match
    variants = {
        "route": route,
        "new": route
        + [feature("R5", [[[-78, 33], [-70, 33], [-70, 38], [-78, 38], [-78, 33]]])],
    }
    amended = copy.deepcopy(route)
    amended[0]["properties"]["rawSigmet"] += " AMD SEV ICE"
    amended[0]["properties"]["hazard"] = "ICE"
    amended[0]["properties"]["issueTime"] = utc(1000)
    variants["amended"] = amended
    cancelled = copy.deepcopy(amended)
    cancelled[0]["properties"]["rawSigmet"] = "KZNY SIGMET R1 CNL SIGMET R1"
    cancelled[0]["properties"]["cancelled"] = True
    variants["cancelled"] = cancelled
    reused = copy.deepcopy(cancelled)
    reused.append(feature("R1", route[0]["geometry"]["coordinates"]))
    reused[-1]["properties"]["validTimeFrom"] = utc(2000)
    reused[-1]["properties"]["validTimeTo"] = utc(10800000)
    variants["reused"] = reused
    variants["empty"] = []
    for name, records in variants.items():
        (root / f"{name}-sigmets.json").write_text(
            json.dumps({"type": "FeatureCollection", "features": records})
        )
    (root / "fixture-manifest.json").write_text(
        json.dumps(
            {
                "generated_at_ms": now,
                "description": "Deterministic source-shaped AWC fixtures, not live observation evidence",
            }
        )
    )
    return now


if __name__ == "__main__":
    generate(Path(sys.argv[1]))
