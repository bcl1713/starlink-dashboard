"""Stable reported bulletin identity must not depend on acquisition or ordering."""

import copy
import importlib

import pytest


def identity():
    return importlib.import_module("app.services.aviation_weather.route_identity")


def feature(identifier="a", **properties):
    return {
        "id": identifier,
        "type": "Feature",
        "properties": {
            "issuer": "TEST",
            "fir": "FIR1",
            "series": "A1-FORECAST",
            "bulletin_series": "A1",
            "revision": None,
            "issued_at_ms": 100,
            "valid_from_ms": 200,
            "valid_to_ms": 2000,
            "expires_at_ms": 2000,
            "phenomenon": "TURB",
            "severity": "SEV",
            "raw_text": "TEST SIGMET A1 SEV TURB FL100/200",
            "vertical": {"lower": 100, "upper": 200, "reference": "FL"},
            "cancelled": False,
            "amends": None,
            "cancellation_target": None,
            **properties,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]]],
        },
    }


def test_refresh_ring_text_and_feature_order_preserve_identity_without_mutation():
    a = feature()
    b = feature("b")
    b["geometry"]["coordinates"][0] = [[3, 3], [3, 0], [0, 0], [0, 3], [3, 3]]
    b["properties"].update(raw_text=" TEST\nSIGMET A1   SEV TURB FL100/200 ")
    original = copy.deepcopy([a, b])
    first = identity().group_bulletins([a, b])
    assert [a, b] == original
    refreshed = identity().group_bulletins([b, a])
    assert len(first) == 1
    assert first[0].feature_ids == ["a", "b"]
    assert first[0].bulletin_key == refreshed[0].bulletin_key
    assert first[0].semantic_digest == refreshed[0].semantic_digest
    assert (
        first[0].semantic_digest == identity().group_bulletins([a])[0].semantic_digest
    )


@pytest.mark.parametrize(
    "change",
    [
        {"revision": "AMD", "issued_at_ms": 150},
        {"severity": "MOD"},
        {"vertical": {"lower": 110, "upper": 200, "reference": "FL"}},
        {"raw_text": "TEST SIGMET A1 SEV TURB FL100/200 MOV E"},
        {"amends": "TEST/FIR1/A0"},
    ],
)
def test_semantic_amendment_changes_digest_but_not_bulletin(change):
    original = identity().group_bulletins([feature()])[0]
    amended = identity().group_bulletins([feature(**change)])[0]
    assert amended.bulletin_key == original.bulletin_key
    assert amended.semantic_digest != original.semantic_digest


def test_series_reuse_and_unknown_issuer_cannot_inherit_identity():
    first = identity().group_bulletins([feature()])[0]
    reused = identity().group_bulletins(
        [feature(valid_from_ms=2200, valid_to_ms=4000, expires_at_ms=4000)]
    )[0]
    assert first.bulletin_key != reused.bulletin_key
    unknown = identity().group_bulletins([feature(issuer=None)])[0]
    changed = identity().group_bulletins([feature(issuer=None, raw_text="other")])[0]
    assert unknown.identity_uncertain
    assert unknown.bulletin_key != changed.bulletin_key


def test_geometry_variants_keep_all_ids_and_distinct_positions():
    a, b = feature(), feature("b")
    b["geometry"]["coordinates"][0][1][0] = 3.0000000001
    combined = identity().group_bulletins([b, a])
    assert len(combined) == 1
    assert combined[0].feature_ids == ["a", "b"]
    assert len(combined[0].geometries) == 2
    assert (
        combined[0].semantic_digest
        != identity().group_bulletins([a])[0].semantic_digest
    )


def test_holes_keep_roles_but_ignore_ring_and_component_order():
    a, b = feature(), feature("b")
    shell = a["geometry"]["coordinates"][0]
    holes = [
        [[1, 1], [1.2, 1], [1, 1.2], [1, 1]],
        [[2, 2], [2.2, 2], [2, 2.2], [2, 2]],
    ]
    a["geometry"]["coordinates"].extend(holes)
    b["geometry"]["coordinates"] = [shell, *reversed(holes)]
    assert (
        identity().group_bulletins([a])[0].semantic_digest
        == identity().group_bulletins([b])[0].semantic_digest
    )
    b["geometry"]["coordinates"] = [holes[0], shell, holes[1]]
    assert (
        identity().group_bulletins([a])[0].semantic_digest
        != identity().group_bulletins([b])[0].semantic_digest
    )

    second = [[[10, 10], [12, 10], [10, 12], [10, 10]]]
    a["geometry"] = {"type": "MultiPolygon", "coordinates": [[shell, *holes], second]}
    b["geometry"] = {
        "type": "MultiPolygon",
        "coordinates": [second, [shell, *reversed(holes)]],
    }
    assert (
        identity().group_bulletins([a])[0].semantic_digest
        == identity().group_bulletins([b])[0].semantic_digest
    )


def test_proven_amendment_retires_predecessor_but_ambiguous_lineage_is_explicit():
    original = feature("original")
    amendment = feature(
        "amended",
        revision="AMD",
        issued_at_ms=150,
        amends="TEST/FIR1/A1",
        raw_text="TEST SIGMET A1 AMD",
    )
    groups = identity().group_bulletins([original, amendment])
    assert len(groups) == 1 and groups[0].feature_ids == ["amended"]
    assert not groups[0].identity_uncertain
    amendment["properties"]["issued_at_ms"] = None
    groups = identity().group_bulletins([original, amendment])
    assert len(groups) == 2
    assert all(group.identity_uncertain for group in groups)
    assert len({group.bulletin_key for group in groups}) == 2
    assert [(g.bulletin_key, g.semantic_digest) for g in groups] == [
        (g.bulletin_key, g.semantic_digest)
        for g in identity().group_bulletins([amendment, original])
    ]


def test_cancellation_evidence_is_retained_without_mutating_source():
    cancelled = feature(
        "cancel",
        cancelled=True,
        cancellation_target={"series": "A1", "valid_from_ms": 200, "valid_to_ms": 2000},
    )
    cancelled["geometry"] = None
    original = copy.deepcopy(cancelled)
    group = identity().group_bulletins([cancelled])[0]
    assert group.properties["cancelled"] is True
    assert (
        group.properties["cancellation_target"]
        == original["properties"]["cancellation_target"]
    )
    assert cancelled == original


def test_numeric_coordinate_equivalence_and_partial_identity_stay_truthful():
    original = feature()
    floats = copy.deepcopy(original)
    floats["id"] = "float"
    floats["geometry"]["coordinates"] = [
        [[float(x), float(y)] for x, y in original["geometry"]["coordinates"][0]]
    ]
    assert (
        identity().group_bulletins([original])[0].semantic_digest
        == identity().group_bulletins([floats])[0].semantic_digest
    )
    assert (
        len(
            identity().group_bulletins(
                [feature("fir1", issuer=None), feature("fir2", issuer=None, fir="FIR2")]
            )
        )
        == 2
    )
