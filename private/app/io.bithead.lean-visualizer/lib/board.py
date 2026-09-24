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

SYSTEM_DIVIDER_KIND = "system-divider"
SYSTEM_DIVIDER_ID = "system-sync-divider"
SYSTEM_DIVIDER_NAME = "Any task below this line will not have its work unit counts queried."
SYSTEM_DIVIDER_COLOR = "#ffe7c2"
VIRTUAL_FEATURE_KIND = "virtual-feature"

MODEL_ID = "default"

CURRENT_MODEL_SCHEMA_VERSION = 1

def default_visualizer_state() -> Dict[str, Any]:
    return {
        "operators": [],
        "tracks": [],
        "backlog": [],
        "releases": [],
        "weeklyNotes": {},
    }

def normalize_visualizer_state(raw_state: Dict[str, Any] | None) -> Dict[str, Any]:
    state = raw_state if isinstance(raw_state, dict) else {}
    operators = state.get("operators")
    tracks = state.get("tracks")
    backlog = state.get("backlog")
    releases = state.get("releases")
    weekly_notes = state.get("weeklyNotes")

    return {
        "operators": operators if isinstance(operators, list) else [],
        "tracks": without_pillar_fields(tracks),
        "backlog": without_pillar_fields(backlog),
        "releases": releases if isinstance(releases, list) else [],
        "weeklyNotes": weekly_notes if isinstance(weekly_notes, dict) else {},
    }

def without_pillar_fields(items: Any) -> List[Any]:
    if not isinstance(items, list):
        return []
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            cleaned.append(item)
            continue
        item = {key: value for key, value in item.items() if key != "pillars"}
        feature = item.get("feature")
        if isinstance(feature, dict):
            item["feature"] = {key: value for key, value in feature.items() if key != "pillars"}
        cleaned.append(item)
    return cleaned

ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")

def normalize_issue_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if ISSUE_KEY_PATTERN.match(text) is None:
        return None
    return text

def issue_key_project(issue_key: str) -> str:
    """ Project key of a normalized issue key: `FR-407` -> `FR`. """
    return str(issue_key).split("-", 1)[0]

def normalize_release_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text == "":
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed.isoformat()

def upgrade_model_state(
    schema_version: int,
    state: Dict[str, Any]
) -> Dict[str, Any]:
    upgraded = normalize_visualizer_state(state)
    current = int(schema_version)

    while current < CURRENT_MODEL_SCHEMA_VERSION:
        if current == 0:
            # Version 0 and 1 currently share the same state shape.
            current = 1
            continue
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model schema version: {current}"
        )

    if current > CURRENT_MODEL_SCHEMA_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Model schema version {current} is newer than supported version {CURRENT_MODEL_SCHEMA_VERSION}",
        )

    return upgraded

def parse_model_state(state_json: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(state_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid model JSON in SQLite store: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=500,
            detail="Invalid model JSON in SQLite store: expected object"
        )
    return parsed

def upsert_model_row(
    conn: sqlite3.Connection,
    state: Dict[str, Any],
    expected_revision: int | None
) -> ModelResponse:
    normalized_state = normalize_visualizer_state(state)
    current_row = read_model_row(conn)

    if current_row is None:
        if expected_revision not in (None, 0):
            raise HTTPException(
                status_code=409,
                detail="Model revision conflict"
            )
        next_revision = 1
    else:
        current_revision = int(current_row["revision"])
        if expected_revision is not None and expected_revision != current_revision:
            raise HTTPException(
                status_code=409,
                detail="Model revision conflict"
            )
        next_revision = current_revision + 1

    write_model_row(
        conn,
        MODEL_ID,
        CURRENT_MODEL_SCHEMA_VERSION,
        json.dumps(normalized_state),
        next_revision,
    )
    conn.commit()

    return ModelResponse(
        schemaVersion=CURRENT_MODEL_SCHEMA_VERSION,
        revision=next_revision,
        state=normalized_state,
        config=ConfigResponse(jiraRootUrl=""),
    )

def read_board_state(conn: sqlite3.Connection) -> Dict[str, Any]:
    ensure_model_table(conn)
    row = read_model_row(conn)
    if row is None:
        return default_visualizer_state()
    parsed = parse_model_state(str(row["state_json"]))
    return upgrade_model_state(int(row["schema_version"]), parsed)
