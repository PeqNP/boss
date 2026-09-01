#
# Scheduler — reading and writing the times a business works in.
#
# A date is `YYYY-MM-DD` and a time is `HH:MM`, both in the business's own
# timezone: a business opens at nine o'clock wherever it is. What a screen
# reads — "Tue Sep 1", "9:00 AM" — is decided here rather than by the screen,
# because a business's day is the server's to define.
#
# Nothing here reaches storage. It is the layer every other one is written on.
#

from datetime import datetime, timedelta
from typing import Optional


def to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def display_time(hhmm: str) -> str:
    """`09:00` as `9:00 AM`, which is how a customer reads a time."""
    minutes = to_minutes(hhmm)
    hour, minute = minutes // 60, minutes % 60
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {suffix}"


def display_date(date: str) -> str:
    """`2026-07-13` as `Monday, July 13`."""
    when = datetime.strptime(date, "%Y-%m-%d")
    return when.strftime("%A, %B ") + str(when.day)


def day_of_week(date: str) -> int:
    """0 for Sunday, matching how schedules and operating hours are stored."""
    return (datetime.strptime(date, "%Y-%m-%d").weekday() + 1) % 7


def overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    """Whether two stretches of a day share any minute.

    Touching is not overlapping: a job ending at 10:00 and one starting at
    10:00 can both happen.
    """
    return start < other_end and other_start < end
