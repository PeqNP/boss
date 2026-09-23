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


def feature_duration_days(feature: Dict[str, Any], capacity: float) -> float | None:
    manual = float(feature.get("manualEstWeeks") or 0)
    if manual > 0:
        return manual * 7
    remaining = max(0, int(feature.get("units") or 0) - int(feature.get("completedUnits") or 0))
    if remaining == 0:
        return 0
    if capacity <= 0:
        return None
    return (remaining / capacity) * 7

def feature_is_open(feature: Any) -> bool:
    """A divider is not work, and a finished feature has no bar."""
    if not isinstance(feature, dict):
        return False
    kind = str(feature.get("kind") or "feature").strip()
    if kind in ("divider", SYSTEM_DIVIDER_KIND):
        return False
    if feature.get("done"):
        return False
    return str(feature.get("name") or "").strip() != ""

def schedule_bar(feature: Dict[str, Any], start: date, capacity: float) -> ScheduleBar:
    span = feature_duration_days(feature, capacity)
    finish = ""
    if span is not None:
        finish = (start + timedelta(days=round(span))).isoformat()
    return ScheduleBar(
        featureId=str(feature.get("id") or ""),
        issueKey=str(feature.get("issueKey") or "").strip(),
        name=str(feature.get("name") or ""),
        color=str(feature.get("color") or ""),
        startOn=start.isoformat(),
        finishOn=finish,
    )

def advance_cursor(start: date, feature: Dict[str, Any], capacity: float) -> date:
    span = feature_duration_days(feature, capacity)
    if span is None:
        return start
    return start + timedelta(days=round(span))

def track_capacity(
    operators: Any,
    rates: Dict[str, RateOperator],
    track_id: str
) -> float:
    total = 0.0
    for item in operators or []:
        if not isinstance(item, dict) or item.get("trackId") != track_id:
            continue
        rate = rates.get(str(item.get("name") or ""))
        if rate is not None:
            total += rate.plannedPerWeek
    return round(total, 2)

def special_track_ids(state: Dict[str, Any], track_ids: set[str]) -> set[str]:
    """A track is special when any feature pins itself to that track."""
    special: set[str] = set()

    def note(feature: Any) -> None:
        if not isinstance(feature, dict):
            return
        pin = str(feature.get("pinnedTrackId") or "")
        if pin in track_ids:
            special.add(pin)

    for raw in state.get("tracks") or []:
        if isinstance(raw, dict):
            note(raw.get("feature"))
    for raw in state.get("backlog") or []:
        note(raw)
    return special

def build_schedule(conn: sqlite3.Connection) -> ScheduleResponse:
    today = local_now().date()
    state = read_board_state(conn)
    _, _, rates, _ = operator_rate_window(conn, today)
    operators = state.get("operators") or []
    tracks: List[ScheduleTrack] = []
    cursors: Dict[str, date] = {}
    for raw in state.get("tracks") or []:
        if not isinstance(raw, dict):
            continue
        track_id = str(raw.get("id") or "")
        capacity = track_capacity(operators, rates, track_id)
        bars: List[ScheduleBar] = []
        cursor = today
        feature = raw.get("feature") if isinstance(raw.get("feature"), dict) else None
        if feature_is_open(feature) and isinstance(feature, dict):
            bars.append(schedule_bar(feature, cursor, capacity))
            cursor = advance_cursor(cursor, feature, capacity)
        cursors[track_id] = cursor
        tracks.append(ScheduleTrack(
            id=track_id,
            name=str(raw.get("name") or ""),
            enabled=bool(raw.get("enabled")),
            capacity=capacity,
            bars=bars,
        ))
    by_id = {track.id: track for track in tracks}
    special = special_track_ids(state, set(by_id))
    general = [
        track for track in tracks
        if track.enabled and track.id not in special and track.capacity > 0
    ]
    if len(general) == 0:
        general = [
            track for track in tracks
            if track.enabled and track.id not in special
        ]
    # Backlog order is priority. Unpinned items are dealt across the ordinary tracks.
    deal = 0
    for raw in state.get("backlog") or []:
        if not feature_is_open(raw) or not isinstance(raw, dict):
            continue
        pin = str(raw.get("pinnedTrackId") or "")
        target = by_id.get(pin)
        if target is None:
            if len(general) == 0:
                continue
            target = general[deal % len(general)]
            deal += 1
        if target is None:
            continue
        start = cursors.get(target.id, today)
        target.bars.append(schedule_bar(raw, start, target.capacity))
        cursors[target.id] = advance_cursor(start, raw, target.capacity)
    releases = []
    for raw in state.get("releases") or []:
        if not isinstance(raw, dict):
            continue
        release_date = normalize_release_date(raw.get("date"))
        version = str(raw.get("version") or "").strip()
        if release_date is None or version == "":
            continue
        releases.append(ScheduleRelease(
            id=str(raw.get("id") or version),
            version=version,
            date=release_date,
        ))
    releases.sort(key=lambda item: (item.date, item.version))
    return ScheduleResponse(horizonDays=180, tracks=tracks, releases=releases)
