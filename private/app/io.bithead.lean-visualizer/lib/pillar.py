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
from .board import SYSTEM_DIVIDER_KIND, VIRTUAL_FEATURE_KIND


PILLAR_NAMES = (
    "Growth / Acquisition",
    "New Features / Retention",
    "Tech Debt / Stability",
    "Process Efficiency / Cost Savings",
    "Unassigned",
)

def store_pillars(conn: sqlite3.Connection, issues: List[Dict[str, Any]]) -> None:
    """Replace the pillars of the issue keys named here. Keys left out stay."""
    ensure_feature_pillars(conn)
    synced_at = local_now().isoformat(timespec="seconds")
    for issue in issues:
        key = str(issue.get("issueKey") or "").strip()
        if key == "":
            continue
        pillars = [str(item) for item in (issue.get("pillars") or []) if str(item).strip() != ""]
        upsert_feature_pillar(conn, key, json.dumps(pillars), synced_at)
    conn.commit()

def pillars_by_issue(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    ensure_feature_pillars(conn)
    rows = feature_pillar_rows(conn)
    found: Dict[str, List[str]] = {}
    for row in rows:
        parsed = json.loads(row["pillars_json"])
        found[str(row["issue_key"])] = parsed if isinstance(parsed, list) else []
    return found

def group_finished(epics: List[Dict[str, Any]]) -> List[PillarFinished]:
    grouped: Dict[str, int] = {}
    for epic in epics:
        pillars = epic.get("pillars") if isinstance(epic.get("pillars"), list) else []
        names = [str(item) for item in pillars if str(item).strip() != ""] or ["Unassigned"]
        for name in names:
            grouped[name] = grouped.get(name, 0) + 1
    return [PillarFinished(pillar=name, featureCount=count) for name, count in sorted(grouped.items())]

def pillar_groups(features: List[Dict[str, Any]]) -> List[PillarOpen]:
    grouped: Dict[str, Dict[str, int]] = {
        name: {"remaining": 0, "count": 0} for name in PILLAR_NAMES
    }
    for feature in features:
        pillars = feature.get("pillars") if isinstance(feature.get("pillars"), list) else []
        names = [str(item) for item in pillars if str(item).strip() != ""] or ["Unassigned"]
        remaining = max(0, int(feature.get("units") or 0) - int(feature.get("completedUnits") or 0))
        for name in names:
            bucket = grouped.setdefault(name, {"remaining": 0, "count": 0})
            bucket["remaining"] += remaining
            bucket["count"] += 1
    order = list(PILLAR_NAMES) + sorted(name for name in grouped if name not in PILLAR_NAMES)
    unique = len(features)
    return [
        PillarOpen(
            pillar=name,
            remainingUnits=grouped[name]["remaining"],
            featureCount=grouped[name]["count"],
            share=(
                0.0 if unique == 0
                else round(grouped[name]["count"] * 100 / unique, 2)
            ),
        )
        for name in order
    ]

def open_features_for_pillars(
    state: Dict[str, Any],
    pillars: Dict[str, List[str]]
) -> List[Dict[str, Any]]:
    """Backlog and track features that have an issue key. Virtual work is left out."""
    candidates: List[Any] = list(state.get("backlog") or [])
    for track in state.get("tracks") or []:
        if isinstance(track, dict):
            candidates.append(track.get("feature"))
    found: List[Dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "feature").strip()
        if kind in ("divider", SYSTEM_DIVIDER_KIND, VIRTUAL_FEATURE_KIND):
            continue
        key = str(raw.get("issueKey") or "").strip()
        if key == "":
            continue
        feature = dict(raw)
        feature["pillars"] = pillars.get(key, [])
        found.append(feature)
    return found
