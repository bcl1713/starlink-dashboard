"""Benchmark reports must describe intervals with no warm upstream queries."""

import asyncio

from benchmark_overview_history import measure


def test_single_sample_on_unchanged_grid_reports_null_query_spans():
    result = asyncio.run(measure(3600, 1, True, 1))
    assert result["warm_queries_two_readers"] == 0
    assert result["warm_evaluation_points_two_readers"] == 0
    assert result["query_span_median_seconds"] is None
    assert result["query_span_max_seconds"] is None
    assert result["second_reader_queries_max"] == 0


def test_single_sample_on_advanced_grid_reports_tail_query_spans():
    result = asyncio.run(measure(1800, 1, True, 1))
    assert result["warm_queries_two_readers"] == 16
    assert result["query_span_median_seconds"] == 11
    assert result["query_span_max_seconds"] == 11
