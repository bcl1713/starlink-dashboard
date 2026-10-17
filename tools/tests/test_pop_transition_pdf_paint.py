"""Actual PDF paths must be visibly filled/stroked before qualifying a band."""

import runpy
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, FloatObject, NameObject

ENTRY = (
    Path(__file__).resolve().parents[2]
    / "tools/acceptance/pop-transitions/pdf_paint.py"
)


def collect(content, alpha=1):
    writer = PdfWriter()
    page = writer.add_blank_page(width=960, height=540)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject()}
    )
    page["/Resources"][NameObject("/ExtGState")] = DictionaryObject(
        {
            NameObject("/Alpha"): DictionaryObject(
                {NameObject("/ca"): FloatObject(alpha)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(content.encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    return runpy.run_path(str(ENTRY))["painted_rectangles"](page)


@pytest.mark.parametrize("paint", ["n", "S", "s"])
def test_unpainted_and_stroke_only_rectangle_cannot_prove_a_filled_band(paint):
    rectangles, _ = collect(f"1 0 0 rg 10 20 30 40 re {paint}")
    assert rectangles == []


@pytest.mark.parametrize("paint", ["f", "F", "f*", "B", "B*", "b", "b*"])
def test_actual_fill_operators_record_fill_at_paint_time(paint):
    rectangles, _ = collect(f"1 0 0 rg 10 20 30 40 re 0 1 0 rg {paint}")
    assert rectangles == [{"bounds": [10, 480, 40, 520], "fill": [0, 1, 0]}]


def test_path_is_not_reused_after_nonpainting_end():
    rectangles, _ = collect("1 0 0 rg 10 20 30 40 re n 60 20 30 40 re f")
    assert rectangles == [{"bounds": [60, 480, 90, 520], "fill": [1, 0, 0]}]


def test_graphics_restore_changes_paint_color_but_retains_current_path():
    rectangles, _ = collect("q 1 0 0 rg 10 20 30 40 re Q f")
    assert rectangles == [{"bounds": [10, 480, 40, 520], "fill": [0, 0, 0]}]


def test_marker_requires_stroke_operator_and_stroke_color_at_paint_time():
    _, absent = collect(".451 .318 .141 RG 10 20 30 40 re n")
    _, present = collect("10 20 30 40 re .451 .318 .141 RG S")
    assert absent == []
    assert present == [[10, 480, 40, 520]]


def test_transform_applies_when_path_is_built_not_when_it_is_painted():
    rectangles, _ = collect("2 0 0 3 5 7 cm 10 20 30 40 re 2 0 0 2 0 0 cm f")
    assert rectangles == [{"bounds": [25, 353, 85, 473], "fill": [0, 0, 0]}]


def test_sheared_path_cannot_prove_its_filled_axis_aligned_bounding_box():
    rectangles, _ = collect("1 1 0 1 0 0 cm 10 20 30 40 re f")
    assert rectangles == []


def test_transparent_fill_cannot_prove_a_visible_color():
    rectangles, _ = collect("/Alpha gs 10 20 30 40 re f", alpha=0)
    assert rectangles == []


def test_clip_is_applied_to_visible_fill_and_restored_by_graphics_state():
    rectangles, _ = collect("q 20 20 10 40 re W n 10 20 30 40 re f Q 10 20 30 40 re f")
    assert rectangles == [
        {"bounds": [20, 480, 30, 520], "fill": [0, 0, 0]},
        {"bounds": [10, 480, 40, 520], "fill": [0, 0, 0]},
    ]


def test_compound_path_with_potential_hole_cannot_prove_a_solid_band():
    rectangles, _ = collect("10 20 30 40 re 15 25 10 10 re f*")
    assert rectangles == []
