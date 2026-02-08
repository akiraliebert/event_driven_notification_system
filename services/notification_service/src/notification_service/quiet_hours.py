"""Quiet hours calculation for deferred notification delivery."""

import datetime
from zoneinfo import ZoneInfo


def calculate_eta(
    quiet_hours_start: datetime.time | None,
    quiet_hours_end: datetime.time | None,
    timezone: str,
    now_utc: datetime.datetime | None = None,
) -> datetime.datetime | None:
    """Calculate Celery ETA if current time falls within quiet hours.

    Returns a UTC datetime for when quiet hours end, or None if delivery
    can proceed immediately.

    Supports wrap-around through midnight (e.g. 22:00 → 08:00).
    """
    if quiet_hours_start is None or quiet_hours_end is None:
        return None

    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.UTC)

    tz = ZoneInfo(timezone)
    now_local = now_utc.astimezone(tz)
    current_time = now_local.time()

    in_quiet = _is_in_quiet_hours(current_time, quiet_hours_start, quiet_hours_end)
    if not in_quiet:
        return None

    # Calculate when quiet hours end in local time
    end_local = now_local.replace(
        hour=quiet_hours_end.hour,
        minute=quiet_hours_end.minute,
        second=0,
        microsecond=0,
    )

    # If end time is before or equal to current time, quiet hours end tomorrow
    if end_local <= now_local:
        end_local += datetime.timedelta(days=1)

    return end_local.astimezone(datetime.UTC)


def _is_in_quiet_hours(
    current: datetime.time,
    start: datetime.time,
    end: datetime.time,
) -> bool:
    """Check if current time is within quiet hours.

    Handles wrap-around: start=22:00, end=08:00 means 22:00→midnight→08:00.
    """
    if start <= end:
        # Simple range: e.g. 01:00 → 06:00
        return start <= current < end
    else:
        # Wrap-around: e.g. 22:00 → 08:00
        return current >= start or current < end
