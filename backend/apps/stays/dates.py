"""
Calendar dates for stays are IST (Asia/Kolkata, UTC+5:30, no daylight saving).

The server and Render's cron run in UTC, so a "day" in India starts at 18:30 UTC the day before: midnight IST on the 30th
is 18:30 UTC on the 29th. Anything that decides which date it is (reminders, "due today", overdue) must go through
today_ist(); the billing engine itself never reads the clock (apps/stays/billing.py).
"""
from datetime import date, datetime, timezone as _utc
from zoneinfo import ZoneInfo

from django.utils import timezone

IST = ZoneInfo('Asia/Kolkata')


def to_ist(moment):
    """A time-zone-aware datetime in IST. A naive datetime is refused: it would hide a time-zone mistake."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError('a timezone-aware datetime is required')
    return moment.astimezone(IST)


def today_ist(now=None):
    """Today's calendar date in India. `now` is for tests and for callers that already hold the current time."""
    return to_ist(now or timezone.now()).date()


def ist_midnight_utc(day):
    """The UTC moment at which `day` begins in India (18:30 UTC the day before): what a UTC cron must wait for."""
    return datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(_utc.utc)


__all__ = ['IST', 'to_ist', 'today_ist', 'ist_midnight_utc', 'date']
