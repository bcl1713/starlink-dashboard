"""Bound route notice admission before expensive geometry or persistence."""

import copy
import importlib

import pytest
from pydantic import ValidationError

from app.services.aviation_weather.settings import (
    AviationSettings,
    AviationSettingsStore,
)
from tests.unit.test_aviation_weather_models import NOW, product


def models():
    return importlib.import_module("app.models.route_sigmets")


def span():
    return {
        "segment_index": 0,
        "start_fraction": 0.25,
        "end_fraction": 0.75,
        "entry": [0.0, 0.0],
        "exit": [1.0, 0.0],
        "boundary_error_m": 18.52,
    }


def context():
    return {
        "context_key": "a" * 64,
        "source": "ordinary",
        "route_id": "route-a",
        "route_name": "Route A",
        "runtime_id": None,
        "run_id": None,
    }


def entry():
    return {
        "notice_key": "b" * 64,
        "bulletin_key": "c" * 64,
        "semantic_digest": "d" * 64,
        "feature_ids": ["f-1"],
        "spans": [span()],
        "encounter": {
            "spans": [
                {
                    "entry_ms": None,
                    "exit_ms": None,
                    "status": "unknown",
                    "reason": "unavailable-plan",
                }
            ],
            "status": "unknown",
            "unknown_count": 1,
            "reason": "unavailable-plan",
        },
        "attention_order": 1,
        "acknowledged": False,
        "valid_from_ms": NOW - 1,
        "expires_at_ms": NOW + 100,
        "identity_uncertain": False,
    }


def snapshot():
    return {
        "schema": "route-sigmets-v2",
        "generated_at_ms": NOW,
        "service_instance_id": "a" * 32,
        "observation_revision": 1,
        "encounter_plan": None,
        "settings_revision": 0,
        "state_revision": 0,
        "generation_id": "e" * 64,
        "context": context(),
        "sigmet_product": product(
            product_type="international-sigmet", representation="advisory-v1"
        ),
        "status": "ready",
        "reason": None,
        "complete": True,
        "truncated": False,
        "entries": [entry()],
        "unresolved": [],
        "future_feature_ids": [],
        "omitted_features": 0,
    }


def test_selected_only_notice_has_no_manufactured_spans():
    payload = entry()
    payload.pop("spans")
    payload.pop("encounter")
    selected = models().SelectedSigmetEntry(**payload)
    assert "spans" not in selected.model_dump()
    with pytest.raises(ValidationError):
        models().SelectedSigmetEntry(**(payload | {"spans": [span()]}))
    with pytest.raises(ValidationError):
        models().RouteSigmetEntry(**(payload | {"spans": []}))


def test_snapshot_cannot_duplicate_bulletins_across_selected_and_matched():
    payload = snapshot()
    selected = entry()
    selected.pop("spans")
    selected.pop("encounter")
    payload["selected_entries"] = [selected]
    with pytest.raises(ValidationError):
        models().RouteSigmetSnapshot(**payload)


def test_legacy_filter_defaults_false(tmp_path):
    assert AviationSettings().sigmet_intersecting_only is False
    store = AviationSettingsStore(tmp_path / "settings.json")
    store.path.write_text('{"sigmet": true, "revision": 7}')
    assert store.get().sigmet_intersecting_only is False
    saved = store.update({"sigmet_intersecting_only": True})
    assert saved.sigmet and saved.sigmet_intersecting_only and saved.revision == 8
    assert store.update({"sigmet_intersecting_only": True}) == saved
    for value in [None, 1, "true"]:
        with pytest.raises(ValueError):
            store.update({"sigmet_intersecting_only": value})
        assert store.get() == saved


def test_wire_context_omits_internal_geometry():
    model = models().RouteContext(**context(), points=[[0.0, 0.0], [1.0, 2.0]])
    assert model.points == [[0.0, 0.0], [1.0, 2.0]]
    assert model.model_dump() == context()


@pytest.mark.parametrize(
    "change",
    [
        {"points": None},
        {"points": [[0.0, 0.0]] * 20001},
        {"points": [[0.0, 91.0]]},
        {"extra": True},
        {"source": "simulation"},
        {"run_id": "run-1"},
    ],
)
def test_context_rejects_unbounded_or_incompatible_identity(change):
    with pytest.raises(ValidationError):
        models().RouteContext(**(context() | {"points": [[0.0, 0.0]]} | change))


@pytest.mark.parametrize(
    "change",
    [
        {"acknowledged": None},
        {"acknowledged": 1},
        {"extra": True},
        {"context_key": "a" * 65},
        {"notice_key": None},
    ],
)
def test_mutation_rejects_untrusted_fields(change):
    payload = {
        "context_key": "a" * 64,
        "notice_key": "b" * 64,
        "semantic_digest": "c" * 64,
        "acknowledged": True,
    }
    with pytest.raises(ValidationError):
        models().NoticeMutation(**(payload | change))


@pytest.mark.parametrize(
    "change",
    [
        {"segment_index": True},
        {"start_fraction": -0.1},
        {"end_fraction": 1.1},
        {"start_fraction": 0.9},
        {"entry": [181.0, 0.0]},
        {"exit": [0.0, float("nan")]},
        {"boundary_error_m": 18.521},
    ],
)
def test_spans_reject_unwitnessed_or_invalid_positions(change):
    with pytest.raises(ValidationError):
        models().IntersectionSpan(**(span() | change))


def test_snapshot_preserves_product_and_accepts_point_contact():
    payload = snapshot()
    payload["entries"][0]["spans"][0]["end_fraction"] = 0.25
    admitted = models().RouteSigmetSnapshot.model_validate(payload)
    assert admitted.sigmet_product.coverage.missing_meaning == "unknown-not-clear"
    assert admitted.entries[0].spans[0].start_fraction == 0.25
    assert admitted.model_dump(by_alias=True)["schema"] == "route-sigmets-v2"


@pytest.mark.parametrize(
    "change",
    [
        {"truncated": True},
        {"truncated": 0},
        {"complete": None},
        {"extra": 0},
        {"generated_at_ms": 9007199254740992},
        {"entries": [entry()] * 501},
        {"entries": [entry(), entry()]},
        {"future_feature_ids": ["f", "f"]},
        {"context": context() | {"source": "simulation"}},
        {"context": context() | {"points": [[0.0, 0.0]]}},
        {"entries": [entry() | {"feature_ids": ["f", "f"]}]},
        {"entries": [entry() | {"expires_at_ms": NOW - 1}]},
        {"entries": [entry() | {"spans": [span()] * 100001}]},
    ],
)
def test_snapshot_rejects_ambiguous_or_excessive_results(change):
    with pytest.raises(ValidationError):
        models().RouteSigmetSnapshot.model_validate(snapshot() | change)


def test_worker_result_uses_features_and_enforces_aggregate_limits():
    payload = {
        "matches": [{"feature_id": "f", "spans": [span()]}],
        "unresolved": [],
        "complete": True,
        "reason": None,
    }
    admitted = models().GeometryResult.model_validate(payload)
    assert admitted.matches[0].feature_id == "f"
    for change in [
        {"matches": payload["matches"] * 2},
        {
            "matches": [
                {"feature_id": str(i), "spans": [span()] * 50001} for i in range(2)
            ]
        },
        {"unresolved": [{"feature_id": "f", "reason": "invented"}]},
        {"unresolved": [{"feature_id": "f", "reason": "limit"}], "complete": True},
    ]:
        with pytest.raises(ValidationError):
            models().GeometryResult.model_validate(copy.deepcopy(payload | change))


def test_snapshot_rejects_aggregate_span_and_encoded_byte_overflow():
    first = entry() | {"spans": [span()] * 50001}
    first["encounter"]["spans"] *= 50001
    first["encounter"]["unknown_count"] = 50001
    second = entry() | {
        "notice_key": "1" * 64,
        "bulletin_key": "2" * 64,
        "feature_ids": ["f-2"],
        "spans": [span()] * 50000,
    }
    second["encounter"]["spans"] *= 50000
    second["encounter"]["unknown_count"] = 50000
    with pytest.raises(ValidationError, match="aggregate spans"):
        models().RouteSigmetSnapshot.model_validate(
            snapshot() | {"entries": [first, second]}
        )
    with pytest.raises(ValidationError, match="8 MiB"):
        models().GeometryResult.model_validate(
            {
                "matches": [{"feature_id": "f", "spans": [span()] * 100000}],
                "unresolved": [],
                "complete": True,
                "reason": None,
            }
        )


def test_snapshot_rejects_combined_feature_limit():
    payload = snapshot() | {
        "entries": [entry() | {"feature_ids": [str(i) for i in range(500)]}],
        "future_feature_ids": ["future"],
    }
    with pytest.raises(ValidationError, match="advisory features"):
        models().RouteSigmetSnapshot.model_validate(payload)


@pytest.mark.parametrize("status", ["off", "no-route", "unavailable"])
def test_inactive_snapshot_needs_no_geometry_or_payload(status):
    payload = snapshot()
    weather = payload["sigmet_product"]
    for key in [
        "observed_at_ms",
        "valid_at_ms",
        "coverage",
        "retrieved_at_ms",
        "fresh_until_ms",
        "expires_at_ms",
        "instance_id",
        "payload",
    ]:
        weather[key] = None
    weather["state"] = "off" if status == "off" else "unavailable"
    payload.update(status=status, context=None, entries=[], complete=False)
    admitted = models().RouteSigmetSnapshot.model_validate(payload)
    assert admitted.context is None and admitted.sigmet_product.payload is None


def test_partial_geometry_preserves_confirmed_matches_and_unknown_gaps():
    admitted = models().GeometryResult.model_validate(
        {
            "matches": [{"feature_id": "f", "spans": [span()]}],
            "unresolved": [{"feature_id": "f", "reason": "boundary-uncertain"}],
            "complete": False,
            "reason": "boundary-uncertain",
        }
    )
    assert admitted.matches[0].spans[0].start_fraction == 0.25
    assert admitted.unresolved[0].reason == "boundary-uncertain"


@pytest.mark.parametrize(
    "change",
    [{"spans": []}, {"unknown_count": 0}, {"status": "overlap"}, {"reason": None}],
)
def test_encounter_evidence_rejects_inconsistent_aggregate(change):
    payload = entry()
    payload["encounter"].update(change)
    with pytest.raises(ValidationError):
        models().RouteSigmetEntry.model_validate(payload)


def test_v2_requires_ordering_and_no_internal_timing_points():
    for field in ("service_instance_id", "observation_revision", "encounter_plan"):
        payload = snapshot()
        payload.pop(field)
        with pytest.raises(ValidationError):
            models().RouteSigmetSnapshot.model_validate(payload)
    with pytest.raises(ValidationError):
        models().RouteSigmetSnapshot.model_validate(
            snapshot() | {"schema": "route-sigmets-v1"}
        )
