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
from .time import *
from .board import *


def operator_rate_window(conn: sqlite3.Connection, today: date) -> tuple[str, str, Dict[str, RateOperator], List[HistoryWeek]]:
    ensure_operator_metrics_table(conn)
    weeks = list(reversed(previous_complete_weeks(today, 8)))
    totals: Dict[str, Dict[str, float]] = {}
    history: List[HistoryWeek] = []
    for sunday in weeks:
        year, week_number = week_identifier_for_date(sunday)
        week_start, week_end = week_bounds_for_date(sunday)
        rows = get_operator_metric_rows(conn, year, week_number)
        operators: List[HistoryOperator] = []
        for name, row in rows.items():
            units = int(row["units_week"] or 0)
            unplanned = int(row["unplanned_work_week"] or 0)
            planned = max(0, units - unplanned)
            bucket = totals.setdefault(name, {"planned": 0.0, "unplanned": 0.0, "weeks": 0})
            bucket["planned"] += planned
            bucket["unplanned"] += unplanned
            bucket["weeks"] += 1
            operators.append(HistoryOperator(operatorName=name, planned=planned, unplanned=unplanned))
        history.append(HistoryWeek(weekStart=week_start, weekEnd=week_end, operators=operators))
    rates = {
        name: RateOperator(
            operatorName=name,
            plannedTotal=int(bucket["planned"]),
            unplannedTotal=int(bucket["unplanned"]),
            plannedPerWeek=round(bucket["planned"] / bucket["weeks"], 2) if bucket["weeks"] else 0,
            unplannedPerWeek=round(bucket["unplanned"] / bucket["weeks"], 2) if bucket["weeks"] else 0,
            weeksCounted=int(bucket["weeks"]),
        )
        for name, bucket in totals.items()
    }
    window_start = history[0].weekStart if history else today.isoformat()
    window_end = history[-1].weekEnd if history else today.isoformat()
    return window_start, window_end, rates, history

def record_operator_week(
    conn: sqlite3.Connection,
    operator_name: str,
    week_start: date,
    units_week: int,
    unplanned_work_week: int,
) -> None:
    """Store one operator week the way the weekly sync does, without calling Jira."""
    ensure_operator_metrics_table(conn)
    year, week_number = week_identifier_for_date(week_start)
    start, end = week_bounds_for_date(week_start)
    replace_operator_metric_week(
        conn,
        operator_name,
        year,
        week_number,
        start,
        start,
        end,
        local_now().isoformat(timespec="seconds"),
        units_week,
        unplanned_work_week,
    )
    conn.commit()
