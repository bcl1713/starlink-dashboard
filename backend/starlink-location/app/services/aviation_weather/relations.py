"""Pure normalized bulletin relations; optional geometry libraries stay unloaded."""


def cancellation_matches(subject: dict, cancellation: dict) -> bool:
    """Match normalized bulletin properties, shared by snapshots and lineage."""
    target = cancellation["cancellation_target"]
    if target is None or not subject["issuer"] or not subject["fir"]:
        return False
    if (subject["issuer"], subject["fir"], subject["bulletin_series"]) != (
        cancellation["issuer"],
        cancellation["fir"],
        target["series"],
    ):
        return False
    if target["valid_from_ms"] is not None:
        if (subject["valid_from_ms"], subject["valid_to_ms"]) != (
            target["valid_from_ms"],
            target["valid_to_ms"],
        ):
            return False
    elif (
        subject["valid_from_ms"] > cancellation["valid_from_ms"]
        or subject["valid_from_ms"] >= cancellation["valid_to_ms"]
        or cancellation["valid_from_ms"] >= subject["valid_to_ms"]
    ):
        return False
    # A marked revision with unknown publication order cannot be attributed to
    # this cancellation safely. Retain its location rather than guess a relation.
    if subject["revision"] is not None and (
        subject["issued_at_ms"] is None or cancellation["issued_at_ms"] is None
    ):
        return False
    # A later published revision survives an older cancellation even when its
    # series/validity are reused. Unknown publication order stays explicit.
    return not (
        subject["issued_at_ms"] is not None
        and cancellation["issued_at_ms"] is not None
        and subject["issued_at_ms"] > cancellation["issued_at_ms"]
    )
