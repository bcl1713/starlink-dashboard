"""Create wholly synthetic public-API inputs; no operational files are read."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def pdf(revision: int, legs: int = 3) -> bytes:
    commands: list[str] = []

    def line(y: int, cells: list[tuple[int, str]]) -> None:
        for x, text in cells:
            text = text.replace("(", r"\(").replace(")", r"\)")
            commands.append(f"BT /F1 9 Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET")

    line(
        570,
        [
            (80, "Mission Itinerary"),
            (
                280,
                f"Mission: SYNTHETIC Revision #: {revision} Aircraft: DEMO Call Sign: TEST",
            ),
        ],
    )
    line(
        545,
        [
            (65, "Departure/Arrival Airport"),
            (245, "Dep/Arr"),
            (280, "Date"),
            (302, "(UTC)"),
            (345, "Adj"),
            (395, "Dep/Arr Date (L)"),
            (625, "Home Dep/Arr"),
        ],
    )
    y = 520
    specs = [
        (
            "AAAA",
            "BBBB",
            "1300",
            "1600",
            [
                ("ALPHA", "13:20Z", "13:40Z"),
                ("BRAVO", "14:10Z", "14:30Z"),
                ("CHARLIE", "15:00Z", "15:20Z"),
            ],
        ),
        ("BBBB", "CCCC", "1800", "1900", []),
        (
            "CCCC",
            "AAAA",
            "2000",
            "2300",
            [("DELTA", "20:20Z", "20:40Z"), ("ECHO", "21:10Z", "21:30Z")],
        ),
    ]
    for ordinal, (departure, arrival, start, end, windows) in enumerate(
        specs[:legs], 1
    ):
        line(
            y, [(55, str(ordinal)), (70, departure), (250, "25-Oct-2026"), (303, start)]
        )
        y -= 15
        line(y, [(70, arrival), (250, "25-Oct-2026"), (303, end)])
        y -= 15
        if windows:
            line(y, [(340, "Air-to-Air Refueling Details")])
            y -= 15
            line(
                y,
                [
                    (110, "AR # Track Details"),
                    (417, "Altitude"),
                    (516, "ARIP"),
                    (636, "AREX"),
                ],
            )
            y -= 15
            for number, (track, entry, exit_time) in enumerate(windows, 1):
                line(
                    y,
                    [
                        (115, str(number)),
                        (140, track),
                        (419, "210"),
                        (489, "25-Oct-2026"),
                        (537, entry),
                        (610, "25-Oct-2026"),
                        (660, exit_time),
                    ],
                )
                y -= 15
    line(
        y - 5,
        [(80, "Total"), (140, "Planned Flight Time"), (489, "07:00"), (610, "hours")],
    )
    stream = "\n".join(commands).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 800 600] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for number, content in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{number} 0 obj\n".encode() + content + b"\nendobj\n"
    startxref = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    result += f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode()
    return result


def kml(ordinal: int, shifted: bool = False) -> bytes:
    start, duration = [(13, 180), (18, 60), (20, 180)][ordinal - 1]
    departure = datetime(2026, 10, 25, start, tzinfo=timezone.utc)
    marks, coordinates = [], []
    for minute in range(0, duration + 1, 10):
        latitude = 35 + minute / 60
        longitude = -100 + (0.01 if shifted else 0)
        coordinate = f"{longitude},{latitude},6400"
        coordinates.append(coordinate)
        clock = (departure + timedelta(minutes=minute)).strftime("%Y-%m-%d %H:%M:%SZ")
        marks.append(
            f"<Placemark><name>Point {minute}</name><description>Time Over Waypoint: {clock}</description><Point><coordinates>{coordinate}</coordinates></Point></Placemark>"
        )
    return (
        '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Synthetic route</name>'
        + "".join(marks)
        + "<Placemark><LineString><coordinates>"
        + " ".join(coordinates)
        + "</coordinates></LineString></Placemark></Document></kml>"
    ).encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    for name, data in [
        ("itinerary.pdf", pdf(1)),
        ("revision.pdf", pdf(2)),
        ("retirement.pdf", pdf(3, 2)),
        ("replacement.kml", kml(1, True)),
    ]:
        (args.output / name).write_bytes(data)
    for ordinal in (1, 2, 3):
        (args.output / f"leg-{ordinal}.kml").write_bytes(kml(ordinal))
    records = []
    for identifier, longitude in [("X-SYNTH-A", -100), ("X-SYNTH-B", -60)]:
        payload = {
            "satellite_id": identifier,
            "transport": "X",
            "longitude": longitude,
            "slot": "Synthetic acceptance only",
            "color": "#FFA500",
        }
        request = Request(
            args.origin + "/api/satellites",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            records.append(json.load(response))
    (args.output / "satellites.json").write_text(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
