"""Lean Visualizer private API."""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from lib import get_config


log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/io.bithead.lean-visualizer")

PRIVATE_CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
COMPLETED_STATUSES = {"done", "won't do", "won’t do", "duplicate"}
MODEL_ID = "default"
CURRENT_MODEL_SCHEMA_VERSION = 1
MODEL_DB_NAME = "lean-visualizer.sqlite3"


def start() -> None:
    logging.info("Starting Lean Visualizer...")
    cfg = get_config()
    os.makedirs(cfg.db_path, exist_ok=True)
    conn = get_model_db_connection()
    try:
        ensure_model_table(conn)
    finally:
        conn.close()


def shutdown() -> None:
    pass


class JiraWorkUnit(BaseModel):
    issueKey: str
    name: str
    totalUnits: int
    completedUnits: int
    issueType: str
    jiraUrl: str


class JiraSyncResponse(BaseModel):
    boardId: int
    jiraRootUrl: str
    issues: List[JiraWorkUnit]


class VisualizerModelResponse(BaseModel):
    schemaVersion: int
    revision: int
    state: Dict[str, Any]


class SaveVisualizerModelRequest(BaseModel):
    revision: int | None = None
    state: Dict[str, Any]


def default_visualizer_state() -> Dict[str, Any]:
    return {
        "operators": [],
        "tracks": [],
        "backlog": [],
        "releases": [],
    }


def normalize_visualizer_state(raw_state: Dict[str, Any] | None) -> Dict[str, Any]:
    state = raw_state if isinstance(raw_state, dict) else {}
    operators = state.get("operators")
    tracks = state.get("tracks")
    backlog = state.get("backlog")
    releases = state.get("releases")

    return {
        "operators": operators if isinstance(operators, list) else [],
        "tracks": tracks if isinstance(tracks, list) else [],
        "backlog": backlog if isinstance(backlog, list) else [],
        "releases": releases if isinstance(releases, list) else [],
    }


def upgrade_model_state(schema_version: int, state: Dict[str, Any]) -> Dict[str, Any]:
    upgraded = normalize_visualizer_state(state)
    current = int(schema_version)

    while current < CURRENT_MODEL_SCHEMA_VERSION:
        if current == 0:
            # Version 0 and 1 currently share the same state shape.
            current = 1
            continue
        raise HTTPException(status_code=400, detail=f"Unsupported model schema version: {current}")

    if current > CURRENT_MODEL_SCHEMA_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Model schema version {current} is newer than supported version {CURRENT_MODEL_SCHEMA_VERSION}",
        )

    return upgraded


def get_model_db_connection() -> sqlite3.Connection:
    cfg = get_config()
    path = os.path.join(cfg.db_path, MODEL_DB_NAME)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_model_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visualizer_models (
            id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            revision INTEGER NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def read_model_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    cursor = conn.execute(
        "SELECT id, schema_version, state_json, revision, updated_at FROM visualizer_models WHERE id = ?",
        (MODEL_ID,),
    )
    return cursor.fetchone()


def parse_model_state(state_json: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(state_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid model JSON in SQLite store: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=500, detail="Invalid model JSON in SQLite store: expected object")
    return parsed


def upsert_model_row(conn: sqlite3.Connection, state: Dict[str, Any], expected_revision: int | None) -> VisualizerModelResponse:
    normalized_state = normalize_visualizer_state(state)
    current_row = read_model_row(conn)

    if current_row is None:
        if expected_revision not in (None, 0):
            raise HTTPException(status_code=409, detail="Model revision conflict")
        next_revision = 1
    else:
        current_revision = int(current_row["revision"])
        if expected_revision is not None and expected_revision != current_revision:
            raise HTTPException(status_code=409, detail="Model revision conflict")
        next_revision = current_revision + 1

    conn.execute(
        """
        INSERT INTO visualizer_models (id, schema_version, state_json, revision, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            schema_version = excluded.schema_version,
            state_json = excluded.state_json,
            revision = excluded.revision,
            updated_at = datetime('now')
        """,
        (
            MODEL_ID,
            CURRENT_MODEL_SCHEMA_VERSION,
            json.dumps(normalized_state),
            next_revision,
        ),
    )
    conn.commit()

    return VisualizerModelResponse(
        schemaVersion=CURRENT_MODEL_SCHEMA_VERSION,
        revision=next_revision,
        state=normalized_state,
    )


def load_config() -> Dict[str, Any]:
    if not PRIVATE_CONFIG_PATH.exists():
        raise HTTPException(status_code=500, detail="Missing config.json for io.bithead.lean-visualizer")

    try:
        config = json.loads(PRIVATE_CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid config.json: {exc}") from exc

    required = ("jira_url", "account_email", "api_key", "board_id")
    for key in required:
        if key not in config or config[key] in (None, ""):
            raise HTTPException(status_code=500, detail=f"config.json is missing {key}")

    return config


def jira_headers(config: Dict[str, Any]) -> Dict[str, str]:
    token = base64.b64encode(f"{config['account_email']}:{config['api_key']}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    }


def jira_root_url(config: Dict[str, Any]) -> str:
    return str(config["jira_url"]).rstrip("/")


def fetch_json(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    started = time.monotonic()
    log.info("jira.fetch.start url=%s", url)

    request = UrlRequest(url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.error("jira.fetch.http_error url=%s status=%s elapsed_ms=%s", url, exc.code, elapsed_ms)
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else exc.reason
        raise HTTPException(status_code=exc.code, detail=f"Jira request failed for {url}: {detail}") from exc
    except URLError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.error("jira.fetch.network_error url=%s elapsed_ms=%s reason=%s", url, elapsed_ms, exc.reason)
        raise HTTPException(status_code=502, detail=f"Jira request failed for {url}: {exc.reason}") from exc

    try:
        body = json.loads(payload)
    except json.JSONDecodeError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.error("jira.fetch.invalid_json url=%s elapsed_ms=%s", url, elapsed_ms)
        raise HTTPException(status_code=502, detail=f"Jira returned invalid JSON for {url}") from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info("jira.fetch.done url=%s elapsed_ms=%s bytes=%s", url, elapsed_ms, len(payload))
    return body


def fetch_all_issues(url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    started = time.monotonic()
    issues: List[Dict[str, Any]] = []
    start_at = 0
    page_count = 0

    while True:
        page_count += 1
        separator = "&" if "?" in url else "?"
        page_url = f"{url}{separator}startAt={start_at}&maxResults=100"
        page_started = time.monotonic()
        payload = fetch_json(page_url, headers)
        page_issues = payload.get("issues", [])
        if not isinstance(page_issues, list):
            page_issues = []

        issues.extend(page_issues)
        page_elapsed_ms = int((time.monotonic() - page_started) * 1000)
        log.info(
            "jira.issues.page url=%s page=%s start_at=%s page_issues=%s elapsed_ms=%s",
            url,
            page_count,
            start_at,
            len(page_issues),
            page_elapsed_ms,
        )

        total = payload.get("total")
        is_last = bool(payload.get("isLast"))
        if is_last or len(page_issues) == 0:
            break

        if isinstance(total, int) and len(issues) >= total:
            break

        start_at = int(payload.get("startAt", start_at)) + len(page_issues)

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info("jira.issues.done url=%s pages=%s total_issues=%s elapsed_ms=%s", url, page_count, len(issues), elapsed_ms)
    return issues


def is_completed_status(status_name: str) -> bool:
    normalized = str(status_name or "").strip().lower()
    return normalized in COMPLETED_STATUSES


def to_work_unit(issue: Dict[str, Any], headers: Dict[str, str], root_url: str) -> JiraWorkUnit | None:
    started = time.monotonic()
    fields = issue.get("fields", {})
    issue_key = str(issue.get("key", "")).strip()
    if issue_key == "":
        return None

    issue_type = str(fields.get("issuetype", {}).get("name", ""))
    if issue_type.lower() != "epic":
        return None

    summary = str(fields.get("summary", issue_key)).strip() or issue_key
    child_url = f"{root_url}/rest/agile/1.0/epic/{quote(issue_key)}/issue?fields=status"
    child_issues = fetch_all_issues(child_url, headers)
    total_units = len(child_issues)
    completed_units = 0

    for child in child_issues:
        child_status = child.get("fields", {}).get("status", {}).get("name", "")
        if is_completed_status(child_status):
            completed_units += 1

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "jira.epic.done key=%s total_units=%s completed_units=%s elapsed_ms=%s",
        issue_key,
        total_units,
        completed_units,
        elapsed_ms,
    )

    return JiraWorkUnit(
        issueKey=issue_key,
        name=summary,
        totalUnits=total_units,
        completedUnits=completed_units,
        issueType=issue_type,
        jiraUrl=f"{root_url}/browse/{quote(issue_key)}",
    )


@router.get("/sync-jira", response_model=JiraSyncResponse)
def sync_jira() -> JiraSyncResponse:
    started = time.monotonic()
    log.info("jira.sync.start")

    config = load_config()
    root_url = jira_root_url(config)
    headers = jira_headers(config)
    board_id = int(config["board_id"])
    board_query = urlencode(
        {
            "fields": "summary,issuetype,status",
            "jql": "issuetype = Epic AND statusCategory != Done ORDER BY Rank ASC",
        }
    )
    board_url = f"{root_url}/rest/agile/1.0/board/{board_id}/issue?{board_query}"
    log.info("jira.sync.board_fetch_start board_id=%s url=%s", board_id, board_url)
    issues = fetch_all_issues(board_url, headers)
    log.info("jira.sync.board_fetch_done board_id=%s issues=%s", board_id, len(issues))

    work_units: List[JiraWorkUnit] = []
    processed_epics = 0
    for issue in issues:
        work_unit = to_work_unit(issue, headers, root_url)
        if work_unit is not None:
            work_units.append(work_unit)
            processed_epics += 1

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info("jira.sync.done board_id=%s epics=%s elapsed_ms=%s", board_id, processed_epics, elapsed_ms)

    return JiraSyncResponse(
        boardId=board_id,
        jiraRootUrl=root_url,
        issues=work_units,
    )


@router.get("/model", response_model=VisualizerModelResponse)
def get_model() -> VisualizerModelResponse:
    conn = get_model_db_connection()
    try:
        row = read_model_row(conn)
        if row is None:
            return VisualizerModelResponse(
                schemaVersion=CURRENT_MODEL_SCHEMA_VERSION,
                revision=0,
                state=default_visualizer_state(),
            )

        raw_schema_version = int(row["schema_version"])
        parsed_state = parse_model_state(str(row["state_json"]))
        migrated_state = upgrade_model_state(raw_schema_version, parsed_state)

        return VisualizerModelResponse(
            schemaVersion=CURRENT_MODEL_SCHEMA_VERSION,
            revision=int(row["revision"]),
            state=migrated_state,
        )
    finally:
        conn.close()


@router.put("/model", response_model=VisualizerModelResponse)
def put_model(body: SaveVisualizerModelRequest) -> VisualizerModelResponse:
    conn = get_model_db_connection()
    try:
        return upsert_model_row(conn, body.state, body.revision)
    finally:
        conn.close()
