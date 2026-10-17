"""Independent PDF-point geometry from full canonical UTC planning windows."""

from datetime import datetime


def verify_markers(boxes, forecast, bounds):
    start, end = [
        datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        for value in bounds
    ]
    # Printed 1280px page, 26px side padding, 1240-unit SVG at 96px/in.
    scale = (1280 - 52) * 0.75 / 1240
    matches = []
    remaining = list(boxes)
    for transition in forecast["transitions"]:
        low = max(
            start,
            datetime.fromisoformat(
                transition["window_start_utc"].replace("Z", "+00:00")
            ).timestamp(),
        )
        high = min(
            end,
            datetime.fromisoformat(
                transition["window_end_utc"].replace("Z", "+00:00")
            ).timestamp(),
        )
        if high <= low:
            continue
        expected = [
            19.5 + (280 + (value - start) / (end - start) * 960) * scale
            for value in (low, high)
        ]
        match = next(
            (
                box
                for box in remaining
                if abs(box[0] - expected[0]) < 1 and abs(box[2] - expected[1]) < 1
            ),
            None,
        )
        if match is None:
            raise ValueError(
                f"PDF marker differs from canonical UTC: expected {expected}, actual {remaining}"
            )
        remaining.remove(match)
        matches.append(
            {"matched": True, "expectedXPt": expected, "actualBoundsPt": match}
        )
    if remaining:
        raise ValueError("Unexpected PDF marker outside canonical UTC windows")
    return matches


def verify_legend(page, boxes):
    """Require the entire short legend line between the marker row and table."""

    def local(element):
        return element.tag.rsplit("}", 1)[-1]

    lines = [element for element in page.iter() if local(element) == "line"]
    table = [
        float(word.attrib["yMin"])
        for line in lines
        for word in line
        if local(word) == "word" and (word.text or "") == "COORDINATION"
    ]
    if not boxes or not table:
        raise ValueError("Missing legend region bounds")
    low, high = max(box[3] for box in boxes), min(table)
    candidates = []
    for line in lines:
        words = [word for word in line if local(word) == "word"]
        if not words:
            continue
        text = " ".join(word.text or "" for word in words)
        if "Starshield" not in text or "Transition" not in text:
            continue
        bounds = [
            min(float(word.attrib["yMin"]) for word in words),
            max(float(word.attrib["yMax"]) for word in words),
        ]
        if low < bounds[0] and bounds[1] < high:
            candidates.append({"text": text, "yBoundsPt": bounds})
    if len(candidates) != 1 or candidates[0]["text"] != "Starshield Transition":
        raise ValueError(f"Invalid exact transition legend: {candidates}")
    return candidates[0]


def verify_bands(rectangles, canonical, marker):
    """Measure filled vector rectangles independently of renderer DOM metadata."""
    colors = {
        "Nominal": "#367755",
        "Degraded": "#e6bd4a",
        "Limited / elevated risk": "#da813a",
        "Communications unavailable": "#b72e36",
        "Posture uncertain": "#dce2e8",
    }

    def rgb(hex_color):
        return [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]

    def clock(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

    start, end = map(clock, canonical["utcBounds"])
    scale = 921 / 1240
    checked = []
    for interval in canonical["intervals"]:
        left, right = [
            19.5 + (280 + (clock(value) - start) / (end - start) * 960) * scale
            for value in (interval["startUtc"], interval["endUtc"])
        ]
        state = interval["decisions"][1]["value"]
        for kind, low, high, color in (
            ("hero", -76, -38, colors[interval["posture"]]),
            (
                "physical Starshield",
                2,
                20,
                (
                    "#899db9"
                    if state == "Down"
                    else "#dce2e8" if state == "?" else "#edf1f5"
                ),
            ),
        ):
            bounds = [left, marker[1] + low * scale, right, marker[1] + high * scale]
            expected_color = rgb(color)
            match = next(
                (
                    rectangle
                    for rectangle in rectangles
                    if all(
                        abs(a - b) < 0.3 for a, b in zip(rectangle["bounds"], bounds)
                    )
                    and all(
                        abs(a - b) < 0.015
                        for a, b in zip(rectangle["fill"], expected_color)
                    )
                ),
                None,
            )
            if match is None:
                raise ValueError(
                    f'Incorrect {kind} band for {interval["startUtc"]}: {bounds}, {color}'
                )
            checked.append({"kind": kind, "boundsPt": bounds, "color": color})
    return {
        "physicalStarshieldVerified": True,
        "conditionalHeroVerified": True,
        "bands": checked,
    }
