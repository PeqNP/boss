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
from .jira import *
from .schedule import *


def store_checkpoint_issues(
    conn: sqlite3.Connection,
    checkpoint_id: int,
    issues: List[Dict[str, Any]],
    operator_names: List[str],
    window_start: str,
    window_end: str,
    developers_field: str,
    trust_window: bool = False,
) -> int:
    """Credit operators for issues that moved to done inside the window.

    A parent makes the credit planned. A developer who is not an operator is skipped.
    """
    start = date.fromisoformat(window_start)
    end = date.fromisoformat(window_end)
    operators = {name for name in operator_names if name != ""}
    credited = 0
    for issue in issues:
        if not trust_window and not issue_completed_in_range(issue, start, end):
            continue
        fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
        issue_key = str(issue.get("key") or "").strip()
        if issue_key == "":
            continue
        parent = parent_task_label(fields)
        planned = 1 if parent else 0
        summary = str(fields.get("summary") or "").strip() or None
        for name in extract_people(fields.get(developers_field)):
            if name not in operators:
                continue
            insert_checkpoint_issue(
                conn,
                checkpoint_id,
                name,
                issue_key,
                summary,
                parent,
                planned,
            )
            credited += 1
    return credited

def read_checkpoint_issues(conn: sqlite3.Connection, release_id: str) -> List[CheckpointIssue]:
    ensure_checkpoint_tables(conn)
    rows = checkpoint_issue_rows(conn, release_id)
    return [
        CheckpointIssue(
            operatorName=str(row["operator_name"]),
            issueKey=str(row["issue_key"]),
            planned=bool(row["planned"]),
        )
        for row in rows
    ]

def checkpoint_window(state: Dict[str, Any], release_id: str) -> tuple[Dict[str, Any], str, str]:
    """The release and the inclusive dates the weekly sync would use for it."""
    release = next((
        item for item in state.get("releases") or []
        if isinstance(item, dict) and str(item.get("id")) == release_id
    ), None)
    if release is None:
        raise HTTPException(status_code=409, detail="That release is not on the board.")
    release_date = normalize_release_date(release.get("date"))
    if release_date is None:
        raise HTTPException(status_code=409, detail="That release has no date.")
    if release_date > local_today_iso():
        raise HTTPException(status_code=409, detail="This release date has not arrived.")
    earlier = [
        normalize_release_date(item.get("date"))
        for item in state.get("releases") or []
        if isinstance(item, dict)
    ]
    previous = [item for item in earlier if item is not None and item < release_date]
    if previous:
        window_start = (date.fromisoformat(max(previous)) + timedelta(days=1)).isoformat()
    else:
        window_start = (date.fromisoformat(release_date) - timedelta(days=13)).isoformat()
    return release, window_start, release_date

def fetch_checkpoint_issues(
    operator_names: List[str],
    window_start: str,
    window_end: str,
) -> tuple[List[Dict[str, Any]], str]:
    """Issues the weekly sync would count for this window, and the Developers field id."""
    config = load_config()
    headers = jira_headers(config)
    planned = get_planned_board_names(config)
    unplanned = get_unplanned_board_names(config)
    scope = planned + [name for name in unplanned if name not in planned]
    field_id = get_developers_field_id(config, headers)
    jql = build_weekly_done_jql(operator_names, scope, window_start, window_end)
    issues = fetch_weekly_done_issues(jira_root_url(config), headers, jql, field_id)
    return issues, field_id

def save_checkpoint(
    conn: sqlite3.Connection,
    release_id: str,
    issues: List[Dict[str, Any]] | None = None,
    developers_field: str = "developers",
    trust_window: bool = False,
) -> CheckpointResponse:
    state = read_board_state(conn)
    release, window_start, release_date = checkpoint_window(state, release_id)
    schedule = build_schedule(conn)
    _, _, rates, _ = operator_rate_window(conn, local_now().date())
    saved_at = local_now().isoformat(timespec="seconds")
    ensure_checkpoint_tables(conn)
    delete_checkpoint_for_release(conn, release_id)
    checkpoint_id = insert_checkpoint(
        conn,
        release_id,
        str(release.get("version") or ""),
        release_date,
        window_start,
        release_date,
        saved_at,
        json.dumps([item.model_dump() for item in rates.values()]),
    )
    operator_names = [
        str(item.get("name") or "").strip()
        for item in state.get("operators") or []
        if isinstance(item, dict)
    ]
    issue_count = store_checkpoint_issues(
        conn,
        checkpoint_id,
        issues or [],
        operator_names,
        window_start,
        release_date,
        developers_field,
        trust_window,
    )
    for track in schedule.tracks:
        for bar in track.bars:
            insert_checkpoint_forecast(
                conn,
                checkpoint_id,
                bar.featureId,
                bar.name,
                bar.color,
                track.id,
                track.name,
                bar.finishOn,
            )
    conn.commit()
    from .snapshot import take_snapshot
    take_snapshot(conn, "checkpoint")
    return CheckpointResponse(
        releaseId=release_id,
        releaseVersion=str(release.get("version") or ""),
        releaseDate=release_date,
        windowStart=window_start,
        windowEnd=release_date,
        savedAt=saved_at,
        issueCount=issue_count,
    )
