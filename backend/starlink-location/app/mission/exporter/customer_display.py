"""Canonical plain-text table cells, shared by composition and PDF verification."""


def display_row(row: dict) -> tuple[str, str, str, str]:
    def short(value: str) -> str:
        return value.replace("Commercial Ka", "Ka").replace(
            "X-Band MILSATCOM", "X-Band"
        )

    return (
        row["et"].replace(" ET", ""),
        short(row["impact"]),
        short(row["remaining"].replace(" + ", ", ")),
        {
            "Limited / elevated risk": "Elevated risk",
            "Communications unavailable": "Unavailable",
            "Assessment incomplete": "Incomplete",
        }.get(row["posture"], row["posture"]),
    )
