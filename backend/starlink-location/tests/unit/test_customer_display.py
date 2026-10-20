import importlib

import pytest


def display(row):
    name = "app.mission.exporter.customer_display"
    assert importlib.util.find_spec(name), "Canonical display-cell contract is absent"
    return importlib.import_module(name).display_row(row)


@pytest.mark.parametrize(
    "time,want",
    [
        ("≈ 23:59 31 Oct–00:01 1 Nov", "23:59 - 00:01"),
        ("01:30 EDT–01:30 EST", "01:30 - 01:30"),
        ("12:25:01–12:25:05", "12:25 - 12:25"),
    ],
)
def test_display_cells_preserve_customer_meaning(time, want):
    assert display(
        {
            "et": time,
            "impact": "Commercial Ka + X-Band MILSATCOM unavailable",
            "remaining": "Commercial Ka + Starshield",
            "posture": "Limited / elevated risk",
        }
    ) == (want, "Ka + X-Band down", "Ka, Starshield", "Elevated risk")


@pytest.mark.parametrize(
    "posture,want",
    [
        ("Communications unavailable", "Unavailable"),
        ("Assessment incomplete", "Incomplete"),
        ("Degraded", "Degraded"),
    ],
)
def test_display_shortens_only_customer_posture(posture, want):
    assert display(
        {
            "et": "10:00 ET–10:15 ET",
            "impact": "<script>unsafe</script>",
            "remaining": "None confirmed",
            "posture": posture,
        }
    ) == ("10:00 - 10:15", "<script>unsafe</script>", "None confirmed", want)


@pytest.mark.parametrize(
    "clock,want",
    [
        ("31 Oct 23:59 ET–01 Nov 00:01 ET", "23:59 - 00:01"),
        ("01:30 EDT–01:30 EST", "01:30 - 01:30"),
        ("12:25:01 ET–12:25:05 ET", "12:25 - 12:25"),
    ],
)
def test_table_time_is_minutes_only_while_canonical_clock_stays_exact(clock, want):
    row = {"et": clock, "impact": "SOF", "remaining": "Ka", "posture": "Nominal"}
    assert display(row)[0] == want
    assert row["et"] == clock


@pytest.mark.parametrize(
    "impact,want",
    [
        (
            "Commercial Ka + X-Band MILSATCOM unavailable; Starshield Transition Window",
            "Ka + X-Band down; Starshield Transition Window",
        ),
        (
            "Air refueling; Commercial Ka + Starshield unavailable; Starshield Transition Window",
            "AR; Ka + Starshield down; Starshield Transition Window",
        ),
        (
            "Air refueling; Commercial Ka unavailable; Starshield Transition Window",
            "AR; Ka down; Starshield Transition Window",
        ),
        (
            "Air refueling; Landing SOF; Commercial Ka unavailable; X–Starshield conflict",
            "AR; Landing SOF; Ka down; X–Starshield conflict",
        ),
    ],
)
def test_dense_transition_display_preserves_every_fact_without_mutating_evidence(
    impact, want
):
    row = {
        "et": "10:00 ET–10:15 ET",
        "impact": impact,
        "remaining": "No secure-call transport",
        "posture": "Communications unavailable",
    }
    cells = display(row)
    assert cells == ("10:00 - 10:15", want, "No secure-call transport", "Unavailable")
    assert row["impact"] == impact
