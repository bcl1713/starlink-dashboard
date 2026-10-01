"""Internal source identities for safe incremental Overview reconciliation."""

from app.services.overview_history_prometheus import (
    OverviewHistoryQueryPlan,
    project_overview_history_matrix,
)


def raw_source_identity(payload: dict, plan: OverviewHistoryQueryPlan) -> dict:
    """Track usable labels, bounding ambiguous identities to a rejection marker."""
    identities: dict[str, object] = {}
    for entry in payload["data"]["result"]:
        projected = project_overview_history_matrix(
            {"status": "success", "data": {"resultType": "matrix", "result": [entry]}},
            plan,
        )
        if not projected:
            continue
        metric = next(iter(projected))
        if metric in identities:
            identities[metric] = None  # Multiple usable series, including same labels.
        else:
            identities[metric] = tuple(sorted(entry["metric"].items()))
    return identities
