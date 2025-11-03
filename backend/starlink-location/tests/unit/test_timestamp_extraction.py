"""Unit tests for timestamp extraction utility."""

import pytest
from datetime import datetime
from app.services.kml_parser import extract_timestamp_from_description


class TestTimestampExtraction:
    """Test cases for extracting timestamps from waypoint descriptions."""

    def test_valid_timestamp_extraction(self):
        """Extract valid timestamp from standard format."""
        description = "PHNL\n Time Over Waypoint: 2025-10-27 16:51:13Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 27
        assert result.hour == 16
        assert result.minute == 51
        assert result.second == 13

    def test_timestamp_at_beginning(self):
        """Extract timestamp when at the beginning of description."""
        description = "Time Over Waypoint: 2025-10-27 16:57:55Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 57, 55)

    def test_timestamp_with_extra_whitespace(self):
        """Extract timestamp with extra whitespace variations."""
        description = "Airport\n Time Over Waypoint:   2025-10-27 17:02:32Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 17, 2, 32)

    def test_timestamp_in_multiline_description(self):
        """Extract timestamp from multiline description."""
        description = "Daniel K Inouye International\n Time Over Waypoint: 2025-10-27 16:51:13Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 51, 13)

    def test_none_description(self):
        """Handle None description gracefully."""
        result = extract_timestamp_from_description(None)
        assert result is None

    def test_empty_description(self):
        """Handle empty description gracefully."""
        result = extract_timestamp_from_description("")
        assert result is None

    def test_description_without_timestamp(self):
        """Return None for description without timestamp."""
        description = "APPCH waypoint with no timing data"
        result = extract_timestamp_from_description(description)
        assert result is None

    def test_malformed_timestamp_missing_time(self):
        """Handle malformed timestamp (missing time component)."""
        description = "Airport\n Time Over Waypoint: 2025-10-27Z"
        result = extract_timestamp_from_description(description)
        assert result is None

    def test_malformed_timestamp_wrong_format(self):
        """Handle malformed timestamp (wrong date format)."""
        description = "Airport\n Time Over Waypoint: 10/27/2025 16:51:13Z"
        result = extract_timestamp_from_description(description)
        assert result is None

    def test_malformed_timestamp_invalid_date(self):
        """Handle malformed timestamp (invalid date values)."""
        description = "Airport\n Time Over Waypoint: 2025-13-32 25:61:61Z"
        result = extract_timestamp_from_description(description)
        assert result is None

    def test_multiple_timestamps_extracts_first(self):
        """When multiple timestamps present, extract the first one."""
        description = "Time Over Waypoint: 2025-10-27 16:51:13Z\nOther Time Over Waypoint: 2025-10-27 17:00:00Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 51, 13)

    def test_timestamp_with_surrounding_text(self):
        """Extract timestamp when surrounded by other text."""
        description = "APPCH waypoint\n Time Over Waypoint: 2025-10-27 17:02:32Z\nAlternate routing"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 17, 2, 32)

    def test_timestamp_edge_case_midnight(self):
        """Extract timestamp at midnight."""
        description = "Time Over Waypoint: 2025-10-27 00:00:00Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 0, 0, 0)

    def test_timestamp_edge_case_end_of_day(self):
        """Extract timestamp at end of day."""
        description = "Time Over Waypoint: 2025-10-27 23:59:59Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 23, 59, 59)

    def test_timestamp_leap_year_date(self):
        """Extract timestamp on leap year date."""
        description = "Time Over Waypoint: 2024-02-29 12:30:45Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2024, 2, 29, 12, 30, 45)

    def test_timestamp_single_digit_month_day(self):
        """Extract timestamp with single digit month/day (padded with zero)."""
        description = "Time Over Waypoint: 2025-01-05 09:08:07Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 1, 5, 9, 8, 7)

    def test_timestamp_different_years(self):
        """Extract timestamps from different years."""
        test_cases = [
            ("Time Over Waypoint: 2024-06-15 12:00:00Z", datetime(2024, 6, 15, 12, 0, 0)),
            ("Time Over Waypoint: 2025-06-15 12:00:00Z", datetime(2025, 6, 15, 12, 0, 0)),
            ("Time Over Waypoint: 2026-06-15 12:00:00Z", datetime(2026, 6, 15, 12, 0, 0)),
        ]

        for description, expected in test_cases:
            result = extract_timestamp_from_description(description)
            assert result == expected

    def test_timestamp_case_insensitive_label(self):
        """Timestamp label is case-sensitive (standard format)."""
        description = "Airport\n time over waypoint: 2025-10-27 16:51:13Z"
        result = extract_timestamp_from_description(description)
        # Should not match due to lowercase - our pattern is case-sensitive
        assert result is None

    def test_description_with_extra_newlines(self):
        """Handle description with multiple newlines around timestamp."""
        description = "-TOC-\n\n Time Over Waypoint: 2025-10-27 16:58:51Z\n"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 58, 51)

    def test_long_description_with_timestamp(self):
        """Extract timestamp from long description text."""
        description = (
            "This is a long airport description with lots of information. "
            "The airport is located at a specific coordinate. "
            "Time Over Waypoint: 2025-10-27 16:51:13Z "
            "This is additional information after the timestamp."
        )
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 51, 13)


class TestTimestampExtractionEdgeCases:
    """Test edge cases and error handling."""

    def test_timestamp_with_tabs(self):
        """Extract timestamp when description uses tabs."""
        description = "Airport\n\tTime Over Waypoint: 2025-10-27 16:51:13Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 51, 13)

    def test_timestamp_almost_correct_format_missing_z(self):
        """Malformed timestamp missing 'Z' suffix."""
        description = "Time Over Waypoint: 2025-10-27 16:51:13"
        result = extract_timestamp_from_description(description)
        assert result is None

    def test_timestamp_almost_correct_format_extra_z(self):
        """Malformed timestamp with extra 'Z' characters."""
        description = "Time Over Waypoint: 2025-10-27 16:51:13ZZ"
        result = extract_timestamp_from_description(description)
        # Should still match because pattern looks for Z at end, but text has ZZ
        result = extract_timestamp_from_description(description)
        assert result is not None  # Pattern will match the first Z

    def test_empty_string_description(self):
        """Empty string should return None."""
        result = extract_timestamp_from_description("")
        assert result is None

    def test_whitespace_only_description(self):
        """Whitespace-only description should return None."""
        result = extract_timestamp_from_description("   \n  \t  ")
        assert result is None


class TestTimestampExtractionRealWorldExamples:
    """Test with real-world KML data examples."""

    def test_phnl_destination_timestamp(self):
        """Extract from real PHNL destination waypoint."""
        description = "Daniel K Inouye International\n Time Over Waypoint: 2025-10-27 16:51:13Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 51, 13)

    def test_appch_waypoint_timestamp(self):
        """Extract from real APPCH approach waypoint."""
        description = "\n Time Over Waypoint: 2025-10-27 16:57:55Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 57, 55)

    def test_toc_waypoint_timestamp(self):
        """Extract from real -TOC- (Top of Climb) waypoint."""
        description = "-TOC-\n Time Over Waypoint: 2025-10-27 16:58:51Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 16, 58, 51)

    def test_tod_waypoint_timestamp(self):
        """Extract from real -TOD- (Top of Descent) waypoint."""
        description = "-TOD-\n Time Over Waypoint: 2025-10-27 17:10:26Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 17, 10, 26)

    def test_kadw_departure_timestamp(self):
        """Extract from real KADW (departure) waypoint."""
        description = "Andrews Air Force Base\n Time Over Waypoint: 2025-10-27 15:45:00Z"
        result = extract_timestamp_from_description(description)

        assert result is not None
        assert result == datetime(2025, 10, 27, 15, 45, 0)
