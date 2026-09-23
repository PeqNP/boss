"""Lean Visualizer rules."""

import base64
import json
import logging
import random
import re
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException
from lib import get_config

from ..model import *
from ..db import *


def local_now() -> datetime:
    return datetime.now().astimezone()

def local_today_iso() -> str:
    return local_now().date().isoformat()

def week_bounds_for_date(date_value) -> tuple[str, str]:
    days_since_sunday = (date_value.weekday() + 1) % 7
    week_start = date_value - timedelta(days=days_since_sunday)
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()

def week_identifier_for_date(date_value: date) -> tuple[int, int]:
    return date_value.year, int(date_value.strftime("%U"))

def week_bounds_for_identifier(
    metric_year: int,
    metric_week_number: int
) -> tuple[str, str]:
    if metric_week_number < 0 or metric_week_number > 53:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric week number: {metric_week_number}"
        )

    try:
        week_start = datetime.strptime(
            f"{metric_year:04d} {metric_week_number:02d} 0",
            "%Y %U %w"
        ).date()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric year/week combination: {metric_year}/{metric_week_number}",
        ) from exc

    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()

def parse_week_start_iso(week_start: str) -> date:
    text = str(week_start or "").strip()
    if text == "":
        raise HTTPException(
            status_code=400,
            detail="week_start cannot be empty"
        )
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid week_start value: {week_start}"
        ) from exc
    if parsed.weekday() != 6:
        raise HTTPException(
            status_code=400,
            detail="week_start must be a Sunday (start of week)"
        )
    return parsed

def resolve_metrics_week(
    metric_year: int | None,
    metric_week_number: int | None,
    week_start: str | None = None,
) -> tuple[int, int, str, str]:
    current_date = local_now().date()
    current_year, current_week_number = week_identifier_for_date(current_date)

    if week_start is not None and (metric_year is not None or metric_week_number is not None):
        raise HTTPException(
            status_code=400,
            detail="Provide either week_start or metric_year/metric_week_number, not both"
        )

    if week_start is not None:
        week_start_date = parse_week_start_iso(week_start)
        selected_year, selected_week_number = week_identifier_for_date(week_start_date)
        if (selected_year, selected_week_number) > (current_year, current_week_number):
            raise HTTPException(
                status_code=400,
                detail="Cannot view or sync metrics beyond the current calendar week"
            )
        week_end = week_start_date + timedelta(days=6)
        return selected_year, selected_week_number, week_start_date.isoformat(), week_end.isoformat()

    if metric_year is None and metric_week_number is None:
        previous_complete_date = current_date - timedelta(days=7)
        previous_year, previous_week_number = week_identifier_for_date(previous_complete_date)
        week_start, week_end = week_bounds_for_date(previous_complete_date)
        return previous_year, previous_week_number, week_start, week_end

    if metric_year is None or metric_week_number is None:
        raise HTTPException(
            status_code=400,
            detail="metric_year and metric_week_number must be provided together"
        )

    if (metric_year, metric_week_number) > (current_year, current_week_number):
        raise HTTPException(
            status_code=400,
            detail="Cannot view or sync metrics beyond the current calendar week"
        )

    week_start, week_end = week_bounds_for_identifier(
        metric_year,
        metric_week_number
    )
    return metric_year, metric_week_number, week_start, week_end

def parse_jira_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if text == "":
        return None

    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_now().tzinfo)
    return parsed

def is_same_local_date(parsed: datetime | None, target_date) -> bool:
    if parsed is None:
        return False
    return parsed.astimezone().date() == target_date

def is_local_date_in_range(
    parsed: datetime | None,
    start_date: date,
    end_date: date
) -> bool:
    if parsed is None:
        return False
    parsed_date = parsed.astimezone().date()
    return start_date <= parsed_date <= end_date

def current_week_start_iso() -> str:
    current_date = local_now().date()
    week_start, _ = week_bounds_for_date(current_date)
    return week_start

def previous_complete_weeks(today: date, count: int) -> List[date]:
    """Sunday starts of the `count` complete weeks before the week containing today."""
    days_since_sunday = (today.weekday() + 1) % 7
    this_sunday = today - timedelta(days=days_since_sunday)
    return [this_sunday - timedelta(days=7 * (offset + 1)) for offset in range(count)]
