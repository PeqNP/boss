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
from .rate import *
from .pillar import *


HISTORY_START = date(2025, 12, 28)

def read_stored_weeks(conn: sqlite3.Connection, earliest: date) -> List[HistoryWeek]:
    """Weeks actually stored on or after `earliest`, oldest first."""
    ensure_operator_metrics_table(conn)
    rows = operator_weeks_since(conn, earliest.isoformat())
    grouped: Dict[str, HistoryWeek] = {}
    order: List[str] = []
    for row in rows:
        start = str(row["week_start"])
        if start not in grouped:
            grouped[start] = HistoryWeek(
                weekStart=start,
                weekEnd=str(row["week_end"]),
                operators=[],
            )
            order.append(start)
        units = int(row["units_week"] or 0)
        unplanned = int(row["unplanned_work_week"] or 0)
        grouped[start].operators.append(HistoryOperator(
            operatorName=str(row["operator_name"]),
            planned=max(0, units - unplanned),
            unplanned=unplanned,
        ))
    return [grouped[start] for start in order]

def merge_history(window: List[HistoryWeek], stored: List[HistoryWeek]) -> List[HistoryWeek]:
    """The eight-week window, plus any older stored week the report still shows."""
    by_start = {week.weekStart: week for week in stored}
    for week in window:
        by_start.setdefault(week.weekStart, week)
    return [by_start[key] for key in sorted(by_start)]

def build_report(conn: sqlite3.Connection) -> ReportResponse:
    today = local_now().date()
    state = read_board_state(conn)
    window_start, window_end, rates, window_history = operator_rate_window(conn, today)
    for name in get_model_operator_names(conn):
        if name not in rates:
            rates[name] = RateOperator(
                operatorName=name,
                plannedTotal=0,
                unplannedTotal=0,
                plannedPerWeek=0,
                unplannedPerWeek=0,
                weeksCounted=0,
            )
    history = merge_history(window_history, read_stored_weeks(conn, HISTORY_START))
    return ReportResponse(
        asOf=today.isoformat(),
        rates=ReportRates(
            windowStart=window_start,
            windowEnd=window_end,
            operators=sorted(rates.values(), key=lambda item: item.operatorName),
            history=history,
        ),
        pillars=ReportPillars(
            open=pillar_groups(open_features_for_pillars(state, pillars_by_issue(conn))),
            finished=[],
        ),
    )
