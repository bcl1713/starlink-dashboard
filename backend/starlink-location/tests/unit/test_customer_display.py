import importlib

import pytest


def display(row):
    name = "app.mission.exporter.customer_display"
    assert importlib.util.find_spec(name), "Canonical display-cell contract is absent"
    return importlib.import_module(name).display_row(row)


@pytest.mark.parametrize(
    "time", ["≈ 23:59 31 Oct–00:01 1 Nov", "01:30 EDT–01:30 EST", "12:25:01–12:25:05"]
)
def test_display_cells_preserve_accepted_customer_copy(time):
    assert display(
        {
            "et": time,
            "impact": "Commercial Ka + X-Band MILSATCOM unavailable",
            "remaining": "Commercial Ka + Starshield",
            "posture": "Limited / elevated risk",
        }
    ) == (time, "Ka + X-Band unavailable", "Ka, Starshield", "Elevated risk")


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
    ) == ("10:00–10:15", "<script>unsafe</script>", "None confirmed", want)
