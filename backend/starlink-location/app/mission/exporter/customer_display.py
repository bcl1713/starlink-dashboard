"""Canonical plain-text table cells, shared by composition and PDF verification."""

import re


def display_row(row: dict) -> tuple[str, str, str, str]:
    def short(value: str) -> str:
        return value.replace("Commercial Ka", "Ka").replace(
            "X-Band MILSATCOM", "X-Band"
        )

    clocks = re.findall(r"(?<!\d)(\d{2}:\d{2})(?::\d{2})?(?!\d)", row["et"])
    if len(clocks) != 2:
        raise ValueError("Expected two customer table clocks")
    return (
        " - ".join(clocks),
        short(row["impact"]),
        short(row["remaining"].replace(" + ", ", ")),
        {
            "Limited / elevated risk": "Elevated risk",
            "Communications unavailable": "Unavailable",
            "Assessment incomplete": "Incomplete",
        }.get(row["posture"], row["posture"]),
    )
