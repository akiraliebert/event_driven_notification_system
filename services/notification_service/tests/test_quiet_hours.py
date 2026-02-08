"""Tests for quiet hours ETA calculation."""

import datetime

from notification_service.quiet_hours import calculate_eta


class TestCalculateEta:
    def test_no_quiet_hours_returns_none(self) -> None:
        result = calculate_eta(
            quiet_hours_start=None,
            quiet_hours_end=None,
            timezone="UTC",
        )
        assert result is None

    def test_outside_quiet_hours_returns_none(self) -> None:
        """14:00 UTC is outside 22:00–08:00 quiet hours."""
        now = datetime.datetime(2026, 1, 15, 14, 0, tzinfo=datetime.UTC)
        result = calculate_eta(
            quiet_hours_start=datetime.time(22, 0),
            quiet_hours_end=datetime.time(8, 0),
            timezone="UTC",
            now_utc=now,
        )
        assert result is None

    def test_inside_quiet_hours_returns_eta(self) -> None:
        """03:00 UTC is inside 22:00–08:00 quiet hours → ETA = 08:00."""
        now = datetime.datetime(2026, 1, 15, 3, 0, tzinfo=datetime.UTC)
        result = calculate_eta(
            quiet_hours_start=datetime.time(22, 0),
            quiet_hours_end=datetime.time(8, 0),
            timezone="UTC",
            now_utc=now,
        )
        assert result is not None
        assert result == datetime.datetime(2026, 1, 15, 8, 0, tzinfo=datetime.UTC)

    def test_wrap_midnight(self) -> None:
        """23:30 UTC is inside 22:00–08:00 → ETA = next day 08:00."""
        now = datetime.datetime(2026, 1, 15, 23, 30, tzinfo=datetime.UTC)
        result = calculate_eta(
            quiet_hours_start=datetime.time(22, 0),
            quiet_hours_end=datetime.time(8, 0),
            timezone="UTC",
            now_utc=now,
        )
        assert result is not None
        assert result == datetime.datetime(2026, 1, 16, 8, 0, tzinfo=datetime.UTC)

    def test_simple_range_inside(self) -> None:
        """02:00 UTC is inside 01:00–06:00 → ETA = 06:00."""
        now = datetime.datetime(2026, 1, 15, 2, 0, tzinfo=datetime.UTC)
        result = calculate_eta(
            quiet_hours_start=datetime.time(1, 0),
            quiet_hours_end=datetime.time(6, 0),
            timezone="UTC",
            now_utc=now,
        )
        assert result is not None
        assert result == datetime.datetime(2026, 1, 15, 6, 0, tzinfo=datetime.UTC)

    def test_timezone_conversion(self) -> None:
        """19:00 UTC = 14:00 US/Eastern (EST, -5). Quiet: 13:00–15:00 Eastern → ETA = 15:00 Eastern = 20:00 UTC."""
        now = datetime.datetime(2026, 1, 15, 19, 0, tzinfo=datetime.UTC)
        result = calculate_eta(
            quiet_hours_start=datetime.time(13, 0),
            quiet_hours_end=datetime.time(15, 0),
            timezone="US/Eastern",
            now_utc=now,
        )
        assert result is not None
        assert result == datetime.datetime(2026, 1, 15, 20, 0, tzinfo=datetime.UTC)
