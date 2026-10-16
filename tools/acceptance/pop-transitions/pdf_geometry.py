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
