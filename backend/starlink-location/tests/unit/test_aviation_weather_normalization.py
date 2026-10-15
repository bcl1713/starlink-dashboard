"""Public AWC normalization contracts using synthetic source-shaped fixtures."""

import importlib
import json
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import pytest
from shapely.geometry import Point, shape

NOW = 1791288000000  # 2026-10-06 12:00 UTC


def normalizer(name):
    try:
        module = importlib.import_module("app.services.aviation_weather.normalization")
    except ModuleNotFoundError:
        pytest.fail("AWC normalization is not implemented")
    return getattr(module, name)


def stamp(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def metar(station="KTEST", observed=NOW - 60000, **changes):
    fields = {
        "raw_text": "METAR KTEST 061159Z 18010G20KT 10SM BKN010 10/05 A2992",
        "station_id": station,
        "observation_time": stamp(observed),
        "latitude": "40",
        "longitude": "-75",
        "temp_c": "10",
        "dewpoint_c": "5",
        "wind_dir_degrees": "180",
        "wind_speed_kt": "10",
        "wind_gust_kt": "20",
        "visibility_statute_mi": "10",
        "altim_in_hg": "29.92",
        "metar_type": "METAR",
    }
    sky = changes.pop(
        "sky", '<sky_condition sky_cover="BKN" cloud_base_ft_agl="1000"/>'
    )
    fields.update(changes)
    return (
        "<METAR>"
        + "".join(
            f"<{k}>{escape(str(v))}</{k}>" for k, v in fields.items() if v is not None
        )
        + sky
        + "</METAR>"
    )


def xml(records, tag="metars"):
    return (
        f'<response><request_index>0</request_index><data_source name="{tag}"/><errors/>'
        f'<data num_results="{len(records)}">' + "".join(records) + "</data></response>"
    ).encode()


def taf(issued=NOW - 60000, start=NOW - 3600000, end=NOW + 3600000, groups=None):
    groups = groups if groups is not None else [forecast(start, end)]
    return (
        "<TAF><raw_text>TAF KTEST 061130Z 0612/0618 18010KT P6SM SKC TEMPO 0612/0613 2SM RA BKN005</raw_text>"
        f"<station_id>KTEST</station_id><issue_time>{stamp(issued)}</issue_time>"
        f"<valid_time_from>{stamp(start)}</valid_time_from><valid_time_to>{stamp(end)}</valid_time_to>"
        "<latitude>40</latitude><longitude>-75</longitude>" + "".join(groups) + "</TAF>"
    )


def forecast(start=NOW - 3600000, end=NOW + 3600000, **changes):
    fields = {
        "fcst_time_from": stamp(start),
        "fcst_time_to": stamp(end),
        "wind_dir_degrees": "180",
        "wind_speed_kt": "10",
        "visibility_statute_mi": "6+",
    }
    sky = changes.pop("sky", '<sky_condition sky_cover="SKC"/>')
    fields.update(changes)
    return (
        "<forecast>"
        + "".join(
            f"<{k}>{escape(str(v))}</{k}>" for k, v in fields.items() if v is not None
        )
        + sky
        + "</forecast>"
    )


def sigmet(**changes):
    geometry = changes.pop(
        "geometry",
        {
            "type": "Polygon",
            "coordinates": [[[10, 0], [12, 0], [12, 2], [10, 2], [10, 0]]],
        },
    )
    properties = {
        "icaoId": "TEST",
        "firId": "FIR1",
        "firName": "Test FIR",
        "seriesId": "1",
        "hazard": "VA",
        "qualifier": "SEV",
        "validTimeFrom": stamp(NOW - 3600000),
        "validTimeTo": stamp(NOW + 3600000),
        "base": 0,
        "top": 7000,
        "rawSigmet": "TEST SIGMET 1 VALID 061100/061300 SEV VA SFC/FL070",
    }
    properties.update(changes)
    if "rawSigmet" not in changes and "seriesId" in changes:
        properties["rawSigmet"] = properties["rawSigmet"].replace(
            "SIGMET 1 VALID", f'SIGMET {changes["seriesId"]} VALID'
        )
    return {"type": "Feature", "properties": properties, "geometry": geometry}


def geojson(features, **changes):
    return json.dumps(
        dict(type="FeatureCollection", features=features, **changes)
    ).encode()


def test_metar_units_identity_and_original_deadlines():
    result = normalizer("normalize_metar")(xml([metar(wx_string="-RA BR")]), NOW)
    assert result["type"] == "FeatureCollection"
    assert result["feed_completeness"] == "unknown" and result["omitted_features"] == 0
    assert result["source_id"] == "awc" and result["retrieved_at_ms"] == NOW
    feature = result["features"][0]
    assert feature["id"] and feature["geometry"] == {
        "type": "Point",
        "coordinates": [-75.0, 40.0],
    }
    p = feature["properties"]
    assert p["wind_speed_mps"] == pytest.approx(5.144444444)
    assert p["gust_mps"] == pytest.approx(10.288888889)
    assert p["visibility_m"] == pytest.approx(16093.44)
    assert p["ceiling_m"] == pytest.approx(304.8) and p["ceiling_reference"] == "AGL"
    assert p["pressure_pa"] == pytest.approx(101320.75888)
    assert p["temperature_k"] == 283.15 and p["dewpoint_k"] == 278.15
    assert p["weather_codes"] == ["-RA", "BR"] and p["flight_category"] == "MVFR"
    assert p["observed_at_ms"] == NOW - 60000
    assert p["fresh_until_ms"] == NOW + 4440000 and p["expires_at_ms"] == NOW + 7140000
    assert (
        p["issued_at_ms"] is None
        and p["valid_from_ms"] is None
        and p["valid_to_ms"] is None
    )
    assert p["forecast_groups"] == []


def test_missing_values_and_variable_wind_remain_explicit():
    p = normalizer("normalize_metar")(
        xml(
            [
                metar(
                    raw_text="SPECI KTEST 061159Z VRB03KT",
                    metar_type="SPECI",
                    wind_dir_degrees="VRB",
                    wind_gust_kt=None,
                    temp_c=None,
                    dewpoint_c=None,
                    altim_in_hg=None,
                    visibility_statute_mi=None,
                    sky="",
                )
            ]
        ),
        NOW,
    )["features"][0]["properties"]
    assert (
        p["report_type"] == "SPECI"
        and p["wind_variable"] is True
        and p["wind_direction_deg"] is None
    )
    for key in [
        "gust_mps",
        "visibility_m",
        "ceiling_m",
        "pressure_pa",
        "temperature_k",
        "dewpoint_k",
        "flight_category",
    ]:
        assert p[key] is None
    assert p["visibility_lower_bound"] is False


@pytest.mark.parametrize(
    "sky,visibility,category,ceiling",
    [
        ('<sky_condition sky_cover="CLR"/>', "10", "VFR", None),
        ('<sky_condition sky_cover="FEW" cloud_base_ft_agl="200"/>', "10", "VFR", None),
        ("", "10", None, None),
        ('<sky_condition sky_cover="OVC"/>', "10", None, None),
        (
            '<sky_condition sky_cover="OVX"/><vert_vis_ft>400</vert_vis_ft>',
            "10",
            "LIFR",
            121.92,
        ),
        ('<sky_condition sky_cover="OVC" cloud_base_ft_agl="500"/>', "3", "IFR", 152.4),
        (
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="3000"/>',
            "5",
            "MVFR",
            914.4,
        ),
        ('<sky_condition sky_cover="SKC"/>', "6+", "VFR", None),
        ('<sky_condition sky_cover="SKC"/>', "2+", None, None),
        ("", "0.5", "LIFR", None),
    ],
)
def test_category_does_not_manufacture_clear_or_exact_lower_bound(
    sky, visibility, category, ceiling
):
    p = normalizer("normalize_metar")(
        xml([metar(sky=sky, visibility_statute_mi=visibility)]), NOW
    )["features"][0]["properties"]
    assert p["flight_category"] == category
    if ceiling is None:
        assert p["ceiling_m"] is None
    else:
        assert p["ceiling_m"] == pytest.approx(ceiling)
    assert p["visibility_lower_bound"] == visibility.endswith("+")


def test_metar_half_open_expiry_and_future_skew():
    records = [
        metar("KEEP", NOW - 7200000 + 1),
        metar("EXPIRED", NOW - 7200000),
        metar("FUTURE", NOW + 60001),
        metar("SKEW", NOW + 60000),
    ]
    result = normalizer("normalize_metar")(xml(records), NOW)
    assert {f["properties"]["station_id"] for f in result["features"]} == {
        "KEEP",
        "SKEW",
    }


def test_latest_station_deduplication_and_bounded_worldwide_feed_are_deterministic():
    records = [metar(f"S{i:04d}") for i in range(5002)]
    records += [metar("S0000", NOW - 120000)]
    normalize = normalizer("normalize_metar")
    result = normalize(xml(records), NOW)
    assert len(result["features"]) == 5000
    assert result["feed_completeness"] == "partial" and result["omitted_features"] == 2
    assert result["features"][0]["properties"]["station_id"] == "S0000"
    assert result["features"][0]["properties"]["observed_at_ms"] == NOW - 60000
    assert result == normalize(xml(list(reversed(records))), NOW)


def test_taf_keeps_each_forecast_change_and_probability_without_inheriting_unknowns():
    groups = [
        forecast(),
        forecast(
            NOW,
            NOW + 1800000,
            change_indicator="TEMPO",
            probability="30",
            wind_dir_degrees="VRB",
            wind_speed_kt=None,
            visibility_statute_mi="2",
            wx_string="RA",
            sky='<sky_condition sky_cover="BKN" cloud_base_ft_agl="500"/>',
        ),
    ]
    p = normalizer("normalize_taf")(xml([taf(groups=groups)], "tafs"), NOW)["features"][
        0
    ]["properties"]
    assert p["report_type"] == "TAF" and p["observed_at_ms"] is None
    assert p["issued_at_ms"] == NOW - 60000 and p["valid_from_ms"] == NOW - 3600000
    assert p["valid_to_ms"] == p["expires_at_ms"] == NOW + 3600000
    assert p["fresh_until_ms"] == NOW + 1200000
    assert p["temperature_k"] is None and p["pressure_pa"] is None
    assert p["visibility_lower_bound"] is True and p["flight_category"] == "VFR"
    assert len(p["forecast_groups"]) == 2
    group = p["forecast_groups"][1]
    assert group["change_type"] == "TEMPO" and group["probability"] == 30
    assert group["valid_from_ms"] == NOW and group["valid_to_ms"] == NOW + 1800000
    assert group["wind_variable"] is True and group["wind_speed_mps"] is None
    assert group["ceiling_m"] == 152.4 and group["visibility_m"] == 3218.688
    assert group["weather_codes"] == ["RA"]


def test_taf_expiry_empty_forecasts_invalid_intervals_and_freshness_cap():
    normalize = normalizer("normalize_taf")
    assert normalize(xml([taf(end=NOW)], "tafs"), NOW)["features"] == []
    for record in [
        taf(groups=[]),
        taf(groups=[forecast(start=NOW + 3600000, end=NOW)]),
    ]:
        result = normalize(xml([record], "tafs"), NOW)
        assert result["features"] == [] and result["omitted_features"] == 1
        assert result["feed_completeness"] == "partial"
    p = normalize(
        xml([taf(end=NOW + 60000, groups=[forecast(end=NOW + 60000)])], "tafs"), NOW
    )["features"][0]["properties"]
    assert p["fresh_until_ms"] == NOW + 60000


@pytest.mark.parametrize(
    "source",
    [
        b"<response>",
        b"<html><data/></html>",
        b"<response><errors><error>bad query</error></errors><data/></response>",
        b'<!DOCTYPE response [<!ENTITY x "bad">]><response><data>&x;</data></response>',
        "<response><data/></response>".encode("utf-16"),
        b'<response><data num_results="2"/></response>',
    ],
)
def test_rejects_malformed_or_unsafe_xml(source):
    with pytest.raises(ValueError):
        normalizer("normalize_metar")(source, NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", "NaN"),
        ("longitude", "Infinity"),
        ("latitude", "91"),
        ("station_id", ""),
        ("observation_time", "2026-10-06T12:00:00"),
        ("wind_speed_kt", "NaN"),
    ],
)
def test_invalid_source_station_is_disclosed_as_omitted(field, value):
    result = normalizer("normalize_metar")(xml([metar(**{field: value})]), NOW)
    assert result["features"] == [] and result["omitted_features"] == 1
    assert result["feed_completeness"] == "partial"


def test_input_size_bound_rejects_source_before_parsing():
    source = b" " * (32 * 1024 * 1024 + 1)
    for name in ["normalize_metar", "normalize_taf", "normalize_sigmet"]:
        with pytest.raises(ValueError):
            normalizer(name)(source, NOW)


def test_sigmet_actual_api_fields_vertical_validity_and_revision_identity():
    result = normalizer("normalize_sigmet")(
        geojson([sigmet(rawSigmet="TEST SIGMET 1 AMD SEV VA FL100/FL200")]), NOW
    )
    p = result["features"][0]["properties"]
    assert result["feed_completeness"] == "unknown" and result["omitted_features"] == 0
    assert p["issuer"] == "TEST" and p["fir"] == "FIR1" and p["series"] == "1"
    assert p["phenomenon"] == "VA" and p["severity"] == "SEV" and p["revision"] == "AMD"
    assert p["vertical"] == {
        "lower": 100,
        "upper": 200,
        "reference": "FL",
        "unit": "flight-level",
    }
    assert (
        p["valid_from_ms"] == NOW - 3600000
        and p["expires_at_ms"] == p["valid_to_ms"] == NOW + 3600000
    )
    assert p["cancelled"] is False
    original = normalizer("normalize_sigmet")(geojson([sigmet()]), NOW)
    assert original["features"][0]["id"] != result["features"][0]["id"]


@pytest.mark.parametrize(
    "raw,vertical",
    [
        (
            "TEST FL100/FL200",
            {"lower": 100, "upper": 200, "reference": "FL", "unit": "flight-level"},
        ),
        (
            "TEST SFC/FL070",
            {"lower": None, "upper": 70, "reference": "FL", "unit": "flight-level"},
        ),
        (
            "TEST 1000/5000FT MSL",
            {"lower": 304.8, "upper": 1524.0, "reference": "MSL", "unit": "m"},
        ),
        (
            "TEST 100/500M AGL",
            {"lower": 100, "upper": 500, "reference": "AGL", "unit": "m"},
        ),
        (
            "TEST UNKNOWN BASE TOP",
            {"lower": None, "upper": None, "reference": "unknown", "unit": "unknown"},
        ),
        (
            "TEST FL200/FL100",
            {"lower": None, "upper": None, "reference": "unknown", "unit": "unknown"},
        ),
    ],
)
def test_sigmet_never_infers_numeric_base_top_units(raw, vertical):
    p = normalizer("normalize_sigmet")(geojson([sigmet(rawSigmet=raw)]), NOW)[
        "features"
    ][0]["properties"]
    assert p["vertical"] == vertical


def test_sigmet_cancellation_text_suppresses_matching_series_geometry():
    source = [sigmet(), sigmet(rawSigmet="TEST CNL SIGMET 1"), sigmet(seriesId="2")]
    result = normalizer("normalize_sigmet")(geojson(source), NOW)
    p = [f for f in result["features"] if f["properties"]["cancelled"]]
    assert len(p) == 1 and p[0]["geometry"] is None
    assert p[0]["properties"]["amends"]
    assert [
        f["properties"]["series"]
        for f in result["features"]
        if f["geometry"] is not None
    ] == ["2"]


@pytest.mark.parametrize(
    "geometry",
    [
        None,
        {"type": "Point", "coordinates": [10, 10]},
        {
            "type": "Polygon",
            "coordinates": [[[10, 0], [12, 2], [10, 2], [12, 0], [10, 0]]],
        },
        {
            "type": "Polygon",
            "coordinates": [[[10, 0], [12, float("nan")], [12, 2], [10, 2], [10, 0]]],
        },
    ],
)
def test_invalid_sigmet_geometry_keeps_unlocated_text(geometry):
    f = normalizer("normalize_sigmet")(geojson([sigmet(geometry=geometry)]), NOW)[
        "features"
    ][0]
    assert f["geometry"] is None and f["properties"]["raw_text"]


def test_dateline_split_keeps_interior_and_crossing_holes():
    coordinates = [
        [[170, -10], [-170, -10], [-170, 10], [170, 10], [170, -10]],
        [[174, -2], [178, -2], [178, 2], [174, 2], [174, -2]],
        [[179, 4], [-179, 4], [-179, 6], [179, 6], [179, 4]],
    ]
    output = normalizer("normalize_sigmet")(
        geojson([sigmet(geometry={"type": "Polygon", "coordinates": coordinates})]), NOW
    )
    polygon = shape(output["features"][0]["geometry"])
    assert (
        polygon.geom_type == "MultiPolygon"
        and polygon.is_valid
        and polygon.area == pytest.approx(380)
    )
    for point in [Point(176, 0), Point(179.5, 5), Point(-179.5, 5)]:
        assert not polygon.covers(point)
    assert polygon.covers(Point(172, 0)) and polygon.covers(Point(-172, 0))
    for piece in polygon.geoms:
        for ring in [piece.exterior, *piece.interiors]:
            assert all(
                abs(a[0] - b[0]) <= 180
                for a, b in zip(ring.coords, list(ring.coords)[1:])
            )


@pytest.mark.parametrize("west,east", [(170, 190), (-190, -170)])
def test_provider_unwrapped_longitude_is_split(west, east):
    coords = [[[west, -10], [east, -10], [east, 10], [west, 10], [west, -10]]]
    f = normalizer("normalize_sigmet")(
        geojson([sigmet(geometry={"type": "Polygon", "coordinates": coords})]), NOW
    )["features"][0]
    polygon = shape(f["geometry"])
    assert polygon.geom_type == "MultiPolygon" and polygon.area == 400
    assert polygon.covers(Point(175, 0)) and polygon.covers(Point(-175, 0))


def test_sigmet_half_open_expiry_and_future_interval_retention():
    source = [
        sigmet(seriesId="1", validTimeTo=stamp(NOW)),
        sigmet(seriesId="2", validTimeFrom=stamp(NOW + 60000)),
    ]
    output = normalizer("normalize_sigmet")(geojson(source), NOW)
    assert [f["properties"]["series"] for f in output["features"]] == ["2"]


@pytest.mark.parametrize(
    "source",
    [
        b"{",
        b"[]",
        b'{"type":"FeatureCollection","features":[{}]}',
        geojson([sigmet(validTimeFrom="2026-10-06T12:00:00")]),
        geojson([sigmet(validTimeTo=stamp(NOW - 7200000))]),
    ],
)
def test_invalid_sigmet_source_is_rejected(source):
    with pytest.raises(ValueError):
        normalizer("normalize_sigmet")(source, NOW)


def test_sigmet_feature_and_vertex_budgets_reject_excess_source():
    normalize = normalizer("normalize_sigmet")
    with pytest.raises(ValueError):
        normalize(geojson([sigmet(seriesId=str(i)) for i in range(501)]), NOW)
    ring = [[10, 0]] * 100001
    with pytest.raises(ValueError):
        normalize(
            geojson([sigmet(geometry={"type": "Polygon", "coordinates": [ring]})]), NOW
        )


@pytest.mark.parametrize(
    "sky,known",
    [
        ("", False),
        ('<sky_condition sky_cover="CLR"/>', True),
        ('<sky_condition sky_cover="BKN"/>', False),
    ],
)
def test_explicit_ceiling_evidence_survives_when_visibility_is_missing(sky, known):
    p = normalizer("normalize_metar")(
        xml([metar(sky=sky, visibility_statute_mi=None)]), NOW
    )["features"][0]["properties"]
    assert (
        p["ceiling_m"] is None
        and p["ceiling_known"] is known
        and p["flight_category"] is None
    )
    group = forecast(visibility_statute_mi=None, sky=sky)
    p = normalizer("normalize_taf")(xml([taf(groups=[group])], "tafs"), NOW)[
        "features"
    ][0]["properties"]
    assert (
        p["ceiling_known"] is known
        and p["forecast_groups"][0]["ceiling_known"] is known
    )


def test_surface_below_a_flight_level_is_not_fabricated_fl_zero():
    p = normalizer("normalize_sigmet")(
        geojson([sigmet(rawSigmet="TEST SFC/FL070")]), NOW
    )["features"][0]["properties"]
    assert p["vertical"] == {
        "lower": None,
        "upper": 70,
        "reference": "FL",
        "unit": "flight-level",
    }


def test_actual_awc_singular_source_names_keep_valid_station_beside_sentinel_location():
    raw = xml(
        [metar("BAD", latitude="-99.99", longitude="-99.99"), metar("GOOD")], "metar"
    )
    result = normalizer("normalize_metar")(raw, NOW)
    assert [f["properties"]["station_id"] for f in result["features"]] == ["GOOD"]
    assert result["omitted_features"] == 1 and result["feed_completeness"] == "partial"
    assert len(normalizer("normalize_taf")(xml([taf()], "taf"), NOW)["features"]) == 1


def test_taf_baseline_is_prevailing_group_even_when_tempo_is_first():
    groups = [
        forecast(
            change_indicator="TEMPO",
            wind_dir_degrees=None,
            wind_speed_kt=None,
            sky='<sky_condition sky_cover="BKN" cloud_base_ft_agl="500"/>',
        ),
        forecast(),
    ]
    p = normalizer("normalize_taf")(xml([taf(groups=groups)], "taf"), NOW)["features"][
        0
    ]["properties"]
    assert p["flight_category"] == "VFR" and p["wind_speed_mps"] == pytest.approx(
        5.144444444
    )
    assert p["forecast_groups"][0]["change_type"] == "TEMPO"


def test_taf_station_limit_is_disclosed_after_latest_issue_selection():
    records = [taf().replace("KTEST", f"S{i:04d}") for i in range(5001)]
    result = normalizer("normalize_taf")(xml(records, "taf"), NOW)
    assert len(result["features"]) == 5000 and result["omitted_features"] == 1
    assert result["feed_completeness"] == "partial"


def test_each_taf_group_retains_its_own_visibility_bound():
    groups = [
        forecast(visibility_statute_mi="6+"),
        forecast(change_indicator="TEMPO", visibility_statute_mi="2"),
    ]
    p = normalizer("normalize_taf")(xml([taf(groups=groups)], "tafs"), NOW)["features"][
        0
    ]["properties"]
    assert [g["visibility_lower_bound"] for g in p["forecast_groups"]] == [True, False]


def test_taf_summary_uses_current_fm_after_initial_forecast_expiry():
    groups = [
        forecast(NOW - 3600000, NOW - 600000),
        forecast(
            NOW - 600000,
            NOW + 3600000,
            change_indicator="FM",
            sky='<sky_condition sky_cover="OVC" cloud_base_ft_agl="3000"/>',
        ),
        forecast(
            NOW - 600000,
            NOW + 3600000,
            change_indicator="TEMPO",
            visibility_statute_mi="0.5",
        ),
    ]
    p = normalizer("normalize_taf")(xml([taf(groups=groups)], "taf"), NOW)["features"][
        0
    ]["properties"]
    assert p["flight_category"] == "MVFR" and p["ceiling_m"] == pytest.approx(914.4)
    assert len(p["forecast_groups"]) == 3


@pytest.mark.parametrize(
    "offset,category", [(-60000, "VFR"), (0, "IFR"), (60000, "IFR")]
)
def test_becmg_keeps_completion_boundary_and_changes_summary_when_complete(
    offset, category
):
    groups = [
        forecast(),
        forecast(
            NOW - 600000,
            NOW + 3600000,
            change_indicator="BECMG",
            time_becoming=stamp(NOW),
            visibility_statute_mi="2",
        ),
    ]
    p = normalizer("normalize_taf")(xml([taf(groups=groups)], "taf"), NOW + offset)[
        "features"
    ][0]["properties"]
    assert p["flight_category"] == category
    group = p["forecast_groups"][1]
    assert (
        group["valid_from_ms"] == NOW - 600000 and group["valid_to_ms"] == NOW + 3600000
    )
    assert (
        group["time_becoming_ms"] == NOW
        and p["forecast_groups"][0]["time_becoming_ms"] is None
    )


def test_taf_summary_does_not_promote_future_group_or_probability_into_current_conditions():
    groups = [
        forecast(NOW - 3600000, NOW - 60000),
        forecast(NOW + 60000, NOW + 3600000, change_indicator="FM"),
        forecast(
            NOW - 60000, NOW + 3600000, probability="30", visibility_statute_mi="0.5"
        ),
    ]
    p = normalizer("normalize_taf")(xml([taf(groups=groups)], "taf"), NOW)["features"][
        0
    ]["properties"]
    assert (
        p["flight_category"] is None
        and p["wind_speed_mps"] is None
        and p["ceiling_known"] is False
    )


@pytest.mark.parametrize("completion", [NOW - 600001, NOW + 3600001])
def test_out_of_interval_becmg_completion_discloses_invalid_station(completion):
    groups = [
        forecast(),
        forecast(
            NOW - 600000,
            NOW + 3600000,
            change_indicator="BECMG",
            time_becoming=stamp(completion),
        ),
    ]
    result = normalizer("normalize_taf")(xml([taf(groups=groups)], "taf"), NOW)
    assert result["features"] == [] and result["omitted_features"] == 1


@pytest.mark.parametrize(
    "raw,vertical",
    [
        (
            "TEST FL090/160",
            {"lower": 90, "upper": 160, "reference": "FL", "unit": "flight-level"},
        ),
        (
            "TEST TOP FL540",
            {"lower": None, "upper": 540, "reference": "FL", "unit": "flight-level"},
        ),
        (
            "TEST TOP ABV FL540",
            {"lower": None, "upper": None, "reference": "unknown", "unit": "unknown"},
        ),
        (
            "TEST FL160/090",
            {"lower": None, "upper": None, "reference": "unknown", "unit": "unknown"},
        ),
        (
            "TEST FL090/160 TOP FL540",
            {"lower": None, "upper": None, "reference": "unknown", "unit": "unknown"},
        ),
    ],
)
def test_source_shaped_flight_level_interval_and_exact_top(raw, vertical):
    p = normalizer("normalize_sigmet")(geojson([sigmet(rawSigmet=raw)]), NOW)[
        "features"
    ][0]["properties"]
    assert p["vertical"] == vertical


def test_multitoken_cancellation_targets_shared_bulletin_forecast_sibling():
    raw = "WCPA02 TEST 061100\nFIR1 SIGMET OSCAR 55 VALID 061100/061300 TEST-\nSEV TS TOP FL540"
    cancel = "WCPA02 TEST 061155\nFIR1 SIGMET OSCAR 56 VALID 061155/061300 TEST-\nCNL SIGMET OSCAR 55 061100/061300"
    source = [
        sigmet(seriesId="OSCAR 55", rawSigmet=raw),
        sigmet(seriesId="OSCAR 55F", rawSigmet=raw),
        sigmet(
            seriesId="OSCAR 56", rawSigmet=cancel, validTimeFrom=stamp(NOW - 300000)
        ),
    ]
    result = normalizer("normalize_sigmet")(geojson(source), NOW)
    assert all(f["geometry"] is None for f in result["features"])
    cancelled = next(
        f["properties"] for f in result["features"] if f["properties"]["cancelled"]
    )
    assert cancelled["amends"] == "TEST/FIR1/OSCAR 55"
    assert cancelled["cancellation_target"] == {
        "series": "OSCAR 55",
        "valid_from_ms": NOW - 3600000,
        "valid_to_ms": NOW + 3600000,
    }
    assert cancelled["issued_at_ms"] == NOW - 300000
    assert {
        f["properties"]["bulletin_series"]
        for f in result["features"]
        if not f["properties"]["cancelled"]
    } == {"OSCAR 55"}


def test_cancellation_does_not_remove_reused_series_or_newer_overlapping_revision():
    original = (
        "WCPA02 TEST 061100\nFIR1 SIGMET A2 VALID 061100/061300 TEST-\nSEV TS FL090/160"
    )
    cancel = "WCPA02 TEST 061155\nFIR1 SIGMET A3 VALID 061155/061300 TEST-\nCNL SIGMET A2 061100/061300"
    future = (
        "WCPA02 TEST 061156\nFIR1 SIGMET A2 VALID 061400/061600 TEST-\nSEV TS FL090/160"
    )
    revision = "WCPA02 TEST 061159\nFIR1 SIGMET A2 VALID 061100/061300 TEST-\nAMD SEV TS FL090/160"
    source = [
        sigmet(seriesId="A2", rawSigmet=original),
        sigmet(seriesId="A2F", rawSigmet=original),
        sigmet(seriesId="A3", rawSigmet=cancel, validTimeFrom=stamp(NOW - 300000)),
        sigmet(
            seriesId="A2",
            rawSigmet=future,
            validTimeFrom=stamp(NOW + 7200000),
            validTimeTo=stamp(NOW + 14400000),
        ),
        sigmet(seriesId="A2", rawSigmet=revision),
    ]
    result = normalizer("normalize_sigmet")(geojson(source), NOW)
    located = [
        f["properties"]["raw_text"]
        for f in result["features"]
        if f["geometry"] is not None
    ]
    assert set(located) == {future, revision}


def test_provider_series_ending_f_without_shared_header_is_not_blindly_cancelled():
    source = [
        sigmet(seriesId="A2F", rawSigmet="TEST SIGMET A2F VALID 061100/061300 SEV TS"),
        sigmet(seriesId="A3", rawSigmet="TEST CNL SIGMET A2 061100/061300"),
    ]
    result = normalizer("normalize_sigmet")(geojson(source), NOW)
    assert [
        f["properties"]["series"]
        for f in result["features"]
        if f["geometry"] is not None
    ] == ["A2F"]


def test_known_restrictive_ceiling_bound_survives_an_unknown_extra_layer():
    sky = '<sky_condition sky_cover="BKN" cloud_base_ft_agl="200"/><sky_condition sky_cover="OVC"/>'
    p = normalizer("normalize_metar")(xml([metar(sky=sky)]), NOW)["features"][0][
        "properties"
    ]
    assert p["ceiling_m"] is None and p["ceiling_known"] is False
    assert p["flight_category"] == "LIFR"
    p = normalizer("normalize_taf")(xml([taf(groups=[forecast(sky=sky)])], "taf"), NOW)[
        "features"
    ][0]["properties"]
    assert p["flight_category"] == "LIFR"


def test_cancellation_preserves_marked_revision_when_publication_order_is_unresolved():
    original = "TEST SIGMET A2 VALID 061100/061300 SEV TS"
    revision = "TEST SIGMET A2 VALID 061100/061300 AMD SEV TS"
    source = [
        sigmet(seriesId="A2", rawSigmet=original),
        sigmet(seriesId="A2", rawSigmet=revision),
        sigmet(seriesId="A3", rawSigmet="TEST CNL SIGMET A2 061100/061300"),
    ]
    result = normalizer("normalize_sigmet")(geojson(source), NOW)
    located = [
        f["properties"]["raw_text"]
        for f in result["features"]
        if f["geometry"] is not None
    ]
    assert located == [revision]


def test_shared_cancellation_matching_is_available_without_loading_geos():
    import subprocess
    import sys

    script = """
import sys
class BlockGEOS:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'shapely' or fullname.startswith('shapely.'):
            raise RuntimeError('optional GEOS must not load for pure lineage matching')
sys.meta_path.insert(0, BlockGEOS())
from app.services.aviation_weather.relations import cancellation_matches
subject = dict(issuer='TEST', fir='FIR1', bulletin_series='OSCAR 55',
               valid_from_ms=1000, valid_to_ms=3000, issued_at_ms=1000, revision=None)
cancel = dict(issuer='TEST', fir='FIR1', valid_from_ms=2000, valid_to_ms=3000,
              issued_at_ms=2000, cancellation_target=dict(series='OSCAR 55',
                                                        valid_from_ms=1000, valid_to_ms=3000))
assert cancellation_matches(subject, cancel)
subject['issued_at_ms'] = 2500
assert not cancellation_matches(subject, cancel)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
