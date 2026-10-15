"""Fail-closed evidence admission for the ordinary itinerary workflow."""

REQUIRED = (
    "automatic_import",
    "ordinary_editing",
    "precision_offsets",
    "migration",
    "revision_history",
    "active_protection",
    "package_roundtrip",
    "desktop_mobile",
)


def validate(proof, sha):
    if proof.get("candidate_sha") != sha:
        raise ValueError("Ordinary journey candidate provenance mismatch")
    missing = [key for key in REQUIRED if proof.get(key) is not True]
    if missing:
        raise ValueError("Missing ordinary import evidence: " + ", ".join(missing))
    return True
