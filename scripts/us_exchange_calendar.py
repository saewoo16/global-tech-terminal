"""Reviewed US equity session schedule. Unsupported years fail closed."""
import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')

# Bounded, reviewed schedule, not a perpetual weekday-only calendar.
# Verified 2026-11-08 against both official equity calendars:
# https://www.nyse.com/trade/hours-calendars
# https://www.nasdaq.com/market-activity/stock-market-holiday-schedule
# Refresh this table for a new year or an exceptional exchange closure.
US_HOLIDAYS = {2026: frozenset((
    '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03',
    '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07',
    '2026-11-26', '2026-12-25',
))}
US_EARLY_CLOSES = frozenset(('2026-11-27', '2026-12-24'))


def is_us_session(date):
    assert date.year in US_HOLIDAYS, 'Official US calendar year not reviewed'
    return date.weekday() < 5 and date.isoformat() not in US_HOLIDAYS[date.year]


def us_session_close(date):
    assert is_us_session(date), 'Official US calendar marks a non-trading date'
    return dt.datetime.combine(date, dt.time(13 if date.isoformat() in US_EARLY_CLOSES else 16), ET)


def previous_us_session(date):
    previous = date - dt.timedelta(days=1)
    while not is_us_session(previous):
        previous -= dt.timedelta(days=1)
    return previous


def latest_completed_session(now):
    """Return a completed session, never infer completion from date alone."""
    assert isinstance(now, dt.datetime) and now.tzinfo is not None, 'Current time must include a timezone'
    now = now.astimezone(ET)
    date = now.date()
    if is_us_session(date) and now >= us_session_close(date):
        return date
    return previous_us_session(date)
