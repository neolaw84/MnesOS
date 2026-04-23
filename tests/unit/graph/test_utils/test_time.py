"""
Unit tests for graph/utils/time.py — game time formatting and duration parsing.
"""

import pytest
from datetime import timedelta, datetime

from MnesOS.graph.utils.time import (
    _format_game_time_context,
    _parse_duration_token,
    _coerce_game_time_to_datetime,
)


class TestFormatGameTimeContext:
    def test_returns_empty_when_no_game_time(self):
        result = _format_game_time_context({})
        assert result == ""

    def test_returns_empty_for_other_keys(self):
        result = _format_game_time_context({"player": {"hp": 100}})
        assert result == ""

    def test_returns_snippet_when_game_time_present(self):
        result = _format_game_time_context({"game_time": "2026-04-01T10:00:00"})
        assert "game_time" in result
        assert "In-Game Time Context" in result
        assert "2026-04-01T10:00:00" in result


class TestParseDurationToken:
    # ISO format
    def test_parse_iso_hours(self):
        assert _parse_duration_token("PT2H") == timedelta(hours=2)

    def test_parse_iso_minutes(self):
        assert _parse_duration_token("PT30M") == timedelta(minutes=30)

    def test_parse_iso_seconds(self):
        assert _parse_duration_token("PT45S") == timedelta(seconds=45)

    def test_parse_iso_combined(self):
        assert _parse_duration_token("PT1H30M") == timedelta(hours=1, minutes=30)

    def test_parse_iso_all_components(self):
        assert _parse_duration_token("PT2H15M10S") == timedelta(hours=2, minutes=15, seconds=10)

    def test_parse_iso_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _parse_duration_token("PT")

    # Shorthand format
    def test_parse_shorthand_days(self):
        assert _parse_duration_token("3d") == timedelta(days=3)

    def test_parse_shorthand_hours(self):
        assert _parse_duration_token("5h") == timedelta(hours=5)

    def test_parse_shorthand_minutes(self):
        assert _parse_duration_token("15m") == timedelta(minutes=15)

    def test_parse_shorthand_seconds(self):
        assert _parse_duration_token("90s") == timedelta(seconds=90)

    def test_parse_shorthand_with_space(self):
        assert _parse_duration_token("  10m  ") == timedelta(minutes=10)

    def test_parse_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            _parse_duration_token("forever")

    def test_parse_empty_string_raises(self):
        with pytest.raises(ValueError):
            _parse_duration_token("")


class TestCoerceGameTimeToDT:
    def test_passes_through_datetime_unchanged(self):
        dt = datetime(2026, 4, 1, 12, 0, 0)
        assert _coerce_game_time_to_datetime(dt) == dt

    def test_parses_iso_with_T(self):
        result = _coerce_game_time_to_datetime("2026-04-01T10:30:00")
        assert result == datetime(2026, 4, 1, 10, 30, 0)

    def test_parses_space_separated(self):
        result = _coerce_game_time_to_datetime("2026-04-01 10:30:00")
        assert result == datetime(2026, 4, 1, 10, 30, 0)

    def test_returns_epoch_for_none(self):
        result = _coerce_game_time_to_datetime(None)
        assert result == datetime(2026, 4, 1, 0, 0, 0)

    def test_returns_epoch_for_empty_string(self):
        result = _coerce_game_time_to_datetime("")
        assert result == datetime(2026, 4, 1, 0, 0, 0)

    def test_returns_epoch_for_junk(self):
        result = _coerce_game_time_to_datetime("not a date at all")
        assert result == datetime(2026, 4, 1, 0, 0, 0)

    def test_returns_epoch_for_integer(self):
        result = _coerce_game_time_to_datetime(12345)
        assert result == datetime(2026, 4, 1, 0, 0, 0)
