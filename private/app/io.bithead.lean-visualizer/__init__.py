"""Lean Visualizer private API."""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import time
from datetime import date, datetime, timedelta
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
COMPLETED_STATUSES = {
    "done",
    "deployed - prod",
    "released to public",
    "won't do",
    "duplicate",
}
COMPLETED_TRANSITION_STATUSES = COMPLETED_STATUSES
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
        ensure_operator_metrics_table(conn)
        ensure_operator_metric_tasks_table(conn)
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


class JiraSyncResponse(BaseModel):
    boardId: int
    jiraRootUrl: str
    issues: List[JiraWorkUnit]


class ConfigResponse(BaseModel):
    jiraRootUrl: str


class ModelResponse(BaseModel):
    schemaVersion: int
    revision: int
    state: Dict[str, Any]
    config: ConfigResponse


class SaveModelRequest(BaseModel):
    revision: int | None = None
    state: Dict[str, Any]


class OperatorMetricsSummary(BaseModel):
    operatorName: str
    unitsDay: int
    unplannedWorkDay: int
    unitsWeek: int
    unplannedWorkWeek: int
    plannedWorkWeek: int
    metricYear: int | None = None
    metricWeekNumber: int | None = None
    weekStart: str | None = None
    weekEnd: str | None = None
    latestMetricDate: str | None = None
    latestSyncedAt: str | None = None


class MetricsSummaryResponse(BaseModel):
    metricYear: int
    metricWeekNumber: int
    weekStart: str
    weekEnd: str
    currentDate: str
    operators: List[OperatorMetricsSummary]


class MetricsSyncStats(BaseModel):
    metricDate: str
    metricYear: int
    metricWeekNumber: int
    weekStart: str
    weekEnd: str
    syncedAt: str
    completedIssues: int
    operatorCredits: int
    plannedCredits: int
    unplannedCredits: int
    unknownDeveloperAssociations: int
    unknownDeveloperNames: List[str]
    operatorRowsUpdated: int
    issuesScanned: int


class MetricsSyncResponse(BaseModel):
    summary: MetricsSummaryResponse
    stats: MetricsSyncStats


class MetricsWindowResponse(BaseModel):
    windowSize: int
    currentWeekStart: str
    currentWeekEnd: str
    weeks: List[MetricsSummaryResponse]


class OperatorMetricTask(BaseModel):
    issueKey: str
    description: str | None = None
    parentTask: str | None = None
    planned: bool


class OperatorMetricTasks(BaseModel):
    operatorName: str
    tasks: List[OperatorMetricTask]


class MetricsTasksResponse(BaseModel):
    metricYear: int
    metricWeekNumber: int
    weekStart: str
    weekEnd: str
    currentDate: str
    jiraRootUrl: str
    jiraQuery: str
    operators: List[OperatorMetricTasks]


ConfigResponse.model_rebuild()
ModelResponse.model_rebuild()
OperatorMetricsSummary.model_rebuild()
MetricsSummaryResponse.model_rebuild()
MetricsSyncStats.model_rebuild()
MetricsSyncResponse.model_rebuild()
MetricsWindowResponse.model_rebuild()
OperatorMetricTask.model_rebuild()
OperatorMetricTasks.model_rebuild()
MetricsTasksResponse.model_rebuild()


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


def ensure_operator_metrics_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visualizer_operator_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_name TEXT NOT NULL,
            metric_year INTEGER NOT NULL,
            metric_week_number INTEGER NOT NULL,
            metric_date TEXT NOT NULL,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            units_week INTEGER NOT NULL,
            unplanned_work_week INTEGER NOT NULL,
            UNIQUE(operator_name, metric_year, metric_week_number)
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_visualizer_operator_metrics_operator_year_week_unique ON visualizer_operator_metrics(operator_name, metric_year, metric_week_number)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visualizer_operator_metrics_year_week ON visualizer_operator_metrics(metric_year, metric_week_number)"
    )
    conn.commit()


def ensure_operator_metric_tasks_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visualizer_operator_metric_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_name TEXT NOT NULL,
            metric_year INTEGER NOT NULL,
            metric_week_number INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            issue_key TEXT NOT NULL,
            issue_description TEXT,
            parent_task TEXT,
            planned INTEGER NOT NULL,
            synced_at TEXT NOT NULL,
            UNIQUE(operator_name, metric_year, metric_week_number, issue_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visualizer_operator_metric_tasks_year_week ON visualizer_operator_metric_tasks(metric_year, metric_week_number)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visualizer_operator_metric_tasks_operator_year_week ON visualizer_operator_metric_tasks(operator_name, metric_year, metric_week_number)"
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


def upsert_model_row(conn: sqlite3.Connection, state: Dict[str, Any], expected_revision: int | None) -> ModelResponse:
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

    return ModelResponse(
        schemaVersion=CURRENT_MODEL_SCHEMA_VERSION,
        revision=next_revision,
        state=normalized_state,
        config=ConfigResponse(jiraRootUrl=""),
    )


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


def week_bounds_for_identifier(metric_year: int, metric_week_number: int) -> tuple[str, str]:
    if metric_week_number < 0 or metric_week_number > 53:
        raise HTTPException(status_code=400, detail=f"Invalid metric week number: {metric_week_number}")

    try:
        week_start = datetime.strptime(f"{metric_year:04d} {metric_week_number:02d} 0", "%Y %U %w").date()
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
        raise HTTPException(status_code=400, detail="week_start cannot be empty")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid week_start value: {week_start}") from exc
    if parsed.weekday() != 6:
        raise HTTPException(status_code=400, detail="week_start must be a Sunday (start of week)")
    return parsed


def resolve_metrics_week(
    metric_year: int | None,
    metric_week_number: int | None,
    week_start: str | None = None,
) -> tuple[int, int, str, str]:
    current_date = local_now().date()
    current_year, current_week_number = week_identifier_for_date(current_date)

    if week_start is not None and (metric_year is not None or metric_week_number is not None):
        raise HTTPException(status_code=400, detail="Provide either week_start or metric_year/metric_week_number, not both")

    if week_start is not None:
        week_start_date = parse_week_start_iso(week_start)
        selected_year, selected_week_number = week_identifier_for_date(week_start_date)
        if (selected_year, selected_week_number) > (current_year, current_week_number):
            raise HTTPException(status_code=400, detail="Cannot view or sync metrics beyond the current calendar week")
        week_end = week_start_date + timedelta(days=6)
        return selected_year, selected_week_number, week_start_date.isoformat(), week_end.isoformat()

    if metric_year is None and metric_week_number is None:
        previous_complete_date = current_date - timedelta(days=7)
        previous_year, previous_week_number = week_identifier_for_date(previous_complete_date)
        week_start, week_end = week_bounds_for_date(previous_complete_date)
        return previous_year, previous_week_number, week_start, week_end

    if metric_year is None or metric_week_number is None:
        raise HTTPException(status_code=400, detail="metric_year and metric_week_number must be provided together")

    if (metric_year, metric_week_number) > (current_year, current_week_number):
        raise HTTPException(status_code=400, detail="Cannot view or sync metrics beyond the current calendar week")

    week_start, week_end = week_bounds_for_identifier(metric_year, metric_week_number)
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


def is_local_date_in_range(parsed: datetime | None, start_date: date, end_date: date) -> bool:
    if parsed is None:
        return False
    parsed_date = parsed.astimezone().date()
    return start_date <= parsed_date <= end_date


def normalize_name_list(raw_value: Any) -> List[str]:
    if not isinstance(raw_value, list):
        return []

    names: List[str] = []
    seen = set()
    for item in raw_value:
        text = str(item or "").strip()
        if text == "" or text in seen:
            continue
        names.append(text)
        seen.add(text)
    return names


def get_fr_board_id(config: Dict[str, Any]) -> int:
    if "fr_board_id" in config and config["fr_board_id"] not in (None, ""):
        return int(config["fr_board_id"])
    if "board_id" in config and config["board_id"] not in (None, ""):
        return int(config["board_id"])
    raise HTTPException(status_code=500, detail="config.json is missing fr_board_id")


def get_planned_board_names(config: Dict[str, Any]) -> List[str]:
    return normalize_name_list(config.get("planned_board_names"))


def get_unplanned_board_names(config: Dict[str, Any]) -> List[str]:
    return normalize_name_list(config.get("unplanned_board_names"))


def jql_escape_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    return escaped


def build_weekly_done_jql(
    operator_names: List[str],
    project_names: List[str],
    week_start: str,
    week_end: str,
) -> str:
    start_jira = date.fromisoformat(week_start).strftime("%Y-%m-%d")
    end_jira = date.fromisoformat(week_end).strftime("%Y-%m-%d")

    if len(project_names) == 0:
        raise HTTPException(status_code=500, detail="config.json does not define planned_board_names or unplanned_board_names")

    if len(operator_names) == 0:
        raise HTTPException(status_code=400, detail="No operators are defined in the model")

    project_clause_values = []
    for project_name in project_names:
        project_clause_values.append(f'"{jql_escape_value(project_name)}"')

    operator_clause_values = []
    for operator_name in operator_names:
        operator_clause_values.append(f'"{jql_escape_value(operator_name)}"')

    project_clause = ", ".join(project_clause_values)
    operator_clause = ", ".join(operator_clause_values)
    return (
        f"project IN ({project_clause}) "
        f"AND \"Developers[User Picker (multiple users)]\" IN ({operator_clause}) "
        "AND status IN (Done, \"Won't Do\") "
        f"AND status CHANGED TO (Done, \"Won't Do\") DURING (\"{start_jira}\", \"{end_jira}\") "
        "ORDER BY created DESC"
    )


def get_model_operator_names(conn: sqlite3.Connection) -> List[str]:
    row = read_model_row(conn)
    if row is None:
        return []

    state = parse_model_state(str(row["state_json"]))
    operators = state.get("operators", [])
    if not isinstance(operators, list):
        return []

    names: List[str] = []
    seen = set()
    for operator in operators:
        if not isinstance(operator, dict):
            continue
        name = str(operator.get("name", "")).strip()
        if name == "" or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def get_operator_metric_rows(conn: sqlite3.Connection, metric_year: int, metric_week_number: int) -> Dict[str, sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT operator_name,
               metric_year,
               metric_week_number,
               metric_date,
               week_start,
               week_end,
               synced_at,
               units_week,
               unplanned_work_week
        FROM visualizer_operator_metrics
        WHERE metric_year = ? AND metric_week_number = ?
        """,
        (metric_year, metric_week_number),
    )
    rows: Dict[str, sqlite3.Row] = {}
    for row in cursor.fetchall():
        rows[str(row["operator_name"])] = row
    return rows


def get_operator_metric_task_rows(conn: sqlite3.Connection, metric_year: int, metric_week_number: int) -> Dict[str, List[sqlite3.Row]]:
    cursor = conn.execute(
        """
        SELECT operator_name,
               issue_key,
               issue_description,
               parent_task,
               planned
        FROM visualizer_operator_metric_tasks
        WHERE metric_year = ? AND metric_week_number = ?
        ORDER BY issue_key ASC
        """,
        (metric_year, metric_week_number),
    )

    rows_by_operator: Dict[str, List[sqlite3.Row]] = {}
    for row in cursor.fetchall():
        operator_name = str(row["operator_name"])
        if operator_name not in rows_by_operator:
            rows_by_operator[operator_name] = []
        rows_by_operator[operator_name].append(row)
    return rows_by_operator


def build_metrics_summary(
    conn: sqlite3.Connection,
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
) -> MetricsSummaryResponse:
    today = local_now().date()
    summary_year, summary_week_number, summary_week_start, summary_week_end = resolve_metrics_week(
        metric_year,
        metric_week_number,
        week_start,
    )
    metric_rows = get_operator_metric_rows(conn, summary_year, summary_week_number)

    operator_names = get_model_operator_names(conn)

    operators: List[OperatorMetricsSummary] = []
    for operator_name in operator_names:
        row = metric_rows.get(operator_name)
        units_week = int(row["units_week"]) if row and row["units_week"] is not None else 0
        unplanned_work_week = int(row["unplanned_work_week"]) if row and row["unplanned_work_week"] is not None else 0
        operators.append(
            OperatorMetricsSummary(
                operatorName=operator_name,
                unitsDay=0,
                unplannedWorkDay=0,
                unitsWeek=units_week,
                unplannedWorkWeek=unplanned_work_week,
                plannedWorkWeek=max(0, units_week - unplanned_work_week),
                metricYear=int(row["metric_year"]) if row and row["metric_year"] is not None else summary_year,
                metricWeekNumber=int(row["metric_week_number"]) if row and row["metric_week_number"] is not None else summary_week_number,
                weekStart=str(row["week_start"]) if row and row["week_start"] is not None else summary_week_start,
                weekEnd=str(row["week_end"]) if row and row["week_end"] is not None else summary_week_end,
                latestMetricDate=str(row["metric_date"]) if row and row["metric_date"] is not None else None,
                latestSyncedAt=str(row["synced_at"]) if row and row["synced_at"] is not None else None,
            )
        )

    return MetricsSummaryResponse(
        metricYear=summary_year,
        metricWeekNumber=summary_week_number,
        weekStart=summary_week_start,
        weekEnd=summary_week_end,
        currentDate=today.isoformat(),
        operators=operators,
    )


def build_metrics_window(
    conn: sqlite3.Connection,
    week_start: str | None = None,
    window_size: int = 5,
) -> MetricsWindowResponse:
    if window_size < 1 or window_size > 26:
        raise HTTPException(status_code=400, detail="window_size must be between 1 and 26")

    current_week_start = current_week_start_iso()
    current_week_start_date = date.fromisoformat(current_week_start)
    current_week_end = (current_week_start_date + timedelta(days=6)).isoformat()

    if week_start is None:
        selected_week_start = current_week_start
    else:
        _, _, selected_week_start, _ = resolve_metrics_week(None, None, week_start=week_start)

    end_week_start_date = date.fromisoformat(selected_week_start)
    start_week_start_date = end_week_start_date - timedelta(days=(window_size - 1) * 7)

    weeks: List[MetricsSummaryResponse] = []
    for index in range(window_size):
        week_start_date = start_week_start_date + timedelta(days=index * 7)
        weeks.append(build_metrics_summary(conn, week_start=week_start_date.isoformat()))

    return MetricsWindowResponse(
        windowSize=window_size,
        currentWeekStart=current_week_start,
        currentWeekEnd=current_week_end,
        weeks=weeks,
    )


def current_week_start_iso() -> str:
    current_date = local_now().date()
    week_start, _ = week_bounds_for_date(current_date)
    return week_start


def upsert_operator_metrics_rows(
    conn: sqlite3.Connection,
    metric_year: int,
    metric_week_number: int,
    metric_date: str,
    week_start: str,
    week_end: str,
    synced_at: str,
    totals_by_operator: Dict[str, Dict[str, int]],
) -> None:
    conn.execute(
        "DELETE FROM visualizer_operator_metrics WHERE metric_year = ? AND metric_week_number = ?",
        (metric_year, metric_week_number),
    )

    for operator_name, totals in totals_by_operator.items():
        conn.execute(
            """
            INSERT INTO visualizer_operator_metrics (
                operator_name,
                metric_year,
                metric_week_number,
                metric_date,
                week_start,
                week_end,
                synced_at,
                units_week,
                unplanned_work_week
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operator_name,
                metric_year,
                metric_week_number,
                metric_date,
                week_start,
                week_end,
                synced_at,
                int(totals.get("units_week", 0)),
                int(totals.get("unplanned_work_week", 0)),
            ),
        )
    conn.commit()


def upsert_operator_metric_task_rows(
    conn: sqlite3.Connection,
    metric_year: int,
    metric_week_number: int,
    week_start: str,
    week_end: str,
    synced_at: str,
    tasks_by_operator: Dict[str, Dict[str, OperatorMetricTask]],
) -> None:
    conn.execute(
        "DELETE FROM visualizer_operator_metric_tasks WHERE metric_year = ? AND metric_week_number = ?",
        (metric_year, metric_week_number),
    )

    for operator_name, tasks_map in tasks_by_operator.items():
        for task in tasks_map.values():
            conn.execute(
                """
                INSERT INTO visualizer_operator_metric_tasks (
                    operator_name,
                    metric_year,
                    metric_week_number,
                    week_start,
                    week_end,
                    issue_key,
                    issue_description,
                    parent_task,
                    planned,
                    synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operator_name,
                    metric_year,
                    metric_week_number,
                    week_start,
                    week_end,
                    task.issueKey,
                    task.description,
                    task.parentTask,
                    1 if task.planned else 0,
                    synced_at,
                ),
            )
    conn.commit()


def load_config() -> Dict[str, Any]:
    if not PRIVATE_CONFIG_PATH.exists():
        raise HTTPException(status_code=500, detail="Missing config.json for io.bithead.lean-visualizer")

    try:
        config = json.loads(PRIVATE_CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid config.json: {exc}") from exc

    required = ("jira_url", "account_email", "api_key")
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


def get_jira_field_map(config: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, str]:
    root_url = jira_root_url(config)
    fields = fetch_json(f"{root_url}/rest/api/3/field", headers)
    if not isinstance(fields, list):
        return {}

    field_map: Dict[str, str] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_name = str(field.get("name", "")).strip()
        field_id = str(field.get("id", "")).strip()
        if field_name and field_id and field_name not in field_map:
            field_map[field_name] = field_id
    return field_map


def fetch_board_candidate_issues(board_id: int, headers: Dict[str, str], root_url: str, week_start: str, week_end: str) -> List[Dict[str, Any]]:
    start_jira = date.fromisoformat(week_start).strftime("%Y/%m/%d")
    end_jira = date.fromisoformat(week_end).strftime("%Y/%m/%d")
    board_query = urlencode(
        {
            "fields": "summary,status,assignee,parent,updated",
            "jql": f'updated >= "{start_jira}" AND updated <= "{end_jira}"',
        }
    )
    board_url = f"{root_url}/rest/agile/1.0/board/{board_id}/issue?{board_query}"
    return fetch_all_issues(board_url, headers)


def fetch_issue_details(issue_key: str, headers: Dict[str, str], root_url: str, field_ids: List[str]) -> Dict[str, Any]:
    fields = ["summary", "status", "assignee", "parent", "updated"] + field_ids
    field_query = ",".join(fields)
    issue_url = f"{root_url}/rest/api/3/issue/{quote(issue_key)}?fields={quote(field_query)}&expand=changelog"
    return fetch_json(issue_url, headers)


def fetch_weekly_done_issues(root_url: str, headers: Dict[str, str], jql: str) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    query = urlencode(
        {
            "jql": jql,
            "maxResults": "1000",
            "fields": "key,summary,status,parent,project,assignee,updated,\"Developers[User Picker (multiple users)]\"",
            "expand": "names",
        }
    )
    url = f"{root_url}/rest/api/3/search/jql?{query}"
    payload = fetch_json(url, headers)
    issues = payload.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    names = payload.get("names", {})
    if not isinstance(names, dict):
        names = {}
    return issues, names


def metrics_candidate_jql(week_start: str, week_end: str) -> str:
    start_jira = date.fromisoformat(week_start).strftime("%Y/%m/%d")
    end_jira = date.fromisoformat(week_end).strftime("%Y/%m/%d")
    return f'updated >= "{start_jira}" AND updated <= "{end_jira}"'


def parent_task_label(fields: Dict[str, Any]) -> str | None:
    parent = fields.get("parent")
    if not isinstance(parent, dict):
        return None

    parent_key = str(parent.get("key", "")).strip()
    if parent_key != "":
        return parent_key

    parent_fields = parent.get("fields")
    if isinstance(parent_fields, dict):
        parent_summary = str(parent_fields.get("summary", "")).strip()
        if parent_summary != "":
            return parent_summary
    return None


def extract_people(value: Any) -> List[str]:
    names: List[str] = []

    def append_name(person: Any) -> None:
        if isinstance(person, str):
            name = person.strip()
            if name:
                names.append(name)
            return

        if not isinstance(person, dict):
            return

        for key in ("displayName", "name", "value", "emailAddress"):
            raw_name = person.get(key)
            if isinstance(raw_name, str) and raw_name.strip():
                names.append(raw_name.strip())
                return

    if isinstance(value, list):
        for person in value:
            append_name(person)
    else:
        append_name(value)

    deduped: List[str] = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        deduped.append(name)
        seen.add(name)
    return deduped


def issue_completed_in_range(issue: Dict[str, Any], start_date: date, end_date: date) -> bool:
    changelog = issue.get("changelog", {})
    histories = changelog.get("histories", []) if isinstance(changelog, dict) else []
    if not isinstance(histories, list):
        return False

    for history in histories:
        if not isinstance(history, dict):
            continue
        created = parse_jira_datetime(history.get("created"))
        if not is_local_date_in_range(created, start_date, end_date):
            continue
        items = history.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("field", "")).strip().lower() != "status":
                continue
            to_string = str(item.get("toString", "")).strip().lower()
            if to_string in COMPLETED_TRANSITION_STATUSES:
                return True

    return False


def count_metrics_for_issue(
    issue: Dict[str, Any],
    developers_field_key: str | None,
    operator_totals: Dict[str, Dict[str, int]],
    task_rows_by_operator: Dict[str, Dict[str, OperatorMetricTask]] | None,
) -> Dict[str, int]:
    fields = issue.get("fields", {}) if isinstance(issue.get("fields", {}), dict) else {}
    issue_key = str(issue.get("key", "")).strip()
    issue_description = str(fields.get("summary", "")).strip() or None
    parent = fields.get("parent")
    is_unplanned = parent in (None, "")

    developer_value = None
    if developers_field_key is not None and developers_field_key in fields:
        developer_value = fields.get(developers_field_key)
    else:
        developer_value = fields.get("Developers[User Picker (multiple users)]")

    people = extract_people(developer_value)
    if len(people) == 0:
        people = extract_people(fields.get("assignee"))

    matched_people = 0
    unknown_people = 0
    unknown_developer_names: List[str] = []
    for person_name in people:
        if person_name not in operator_totals:
            unknown_people += 1
            unknown_developer_names.append(person_name)
            continue

        operator_totals[person_name]["units_week"] += 1
        if is_unplanned:
            operator_totals[person_name]["unplanned_work_week"] += 1
        if task_rows_by_operator is not None and issue_key != "":
            task_rows_by_operator[person_name][issue_key] = OperatorMetricTask(
                issueKey=issue_key,
                description=issue_description,
                parentTask=parent_task_label(fields),
                planned=not is_unplanned,
            )
        matched_people += 1

    if matched_people == 0 and len(people) == 0:
        unknown_people = 1
        unknown_developer_names.append("Unassigned")

    return {
        "completed_issues": 1,
        "operator_credits": matched_people,
        "planned_credits": 0 if is_unplanned else matched_people,
        "unplanned_credits": matched_people if is_unplanned else 0,
        "unknown_developer_associations": unknown_people,
        "unknown_developer_names": unknown_developer_names,
    }
def sync_task_metrics_response(
    config: Dict[str, Any],
    headers: Dict[str, str],
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
) -> MetricsSyncResponse:
    root_url = jira_root_url(config)
    planned_board_names = get_planned_board_names(config)
    unplanned_board_names = get_unplanned_board_names(config)
    project_scope = planned_board_names + [name for name in unplanned_board_names if name not in planned_board_names]
    if len(project_scope) == 0:
        raise HTTPException(status_code=500, detail="config.json does not define planned_board_names or unplanned_board_names")

    conn = get_model_db_connection()
    try:
        ensure_operator_metrics_table(conn)
        ensure_operator_metric_tasks_table(conn)
        operator_names = get_model_operator_names(conn)
        totals_by_operator = {
            operator_name: {"units_week": 0, "unplanned_work_week": 0}
            for operator_name in operator_names
        }
        task_rows_by_operator = {
            operator_name: {}
            for operator_name in operator_names
        }

        metric_year, metric_week_number, week_start, week_end = resolve_metrics_week(metric_year, metric_week_number, week_start)
        metric_date = local_today_iso()
        synced_at = local_now().isoformat(timespec="seconds")
        jql = ""
        issues: List[Dict[str, Any]] = []
        names_map: Dict[str, str] = {}

        stats = {
            "completed_issues": 0,
            "operator_credits": 0,
            "planned_credits": 0,
            "unplanned_credits": 0,
            "unknown_developer_associations": 0,
            "unknown_developer_names": set(),
            "issues_scanned": 0,
        }

        if len(operator_names) > 0:
            jql = build_weekly_done_jql(operator_names, project_scope, week_start, week_end)
            issues, names_map = fetch_weekly_done_issues(root_url, headers, jql)

        developers_field_key = None
        for field_key, field_name in names_map.items():
            if str(field_name).strip() == "Developers[User Picker (multiple users)]":
                developers_field_key = str(field_key)
                break

        for issue in issues:
            stats["issues_scanned"] += 1
            issue_stats = count_metrics_for_issue(
                issue,
                developers_field_key,
                totals_by_operator,
                task_rows_by_operator,
            )

            stats["completed_issues"] += issue_stats["completed_issues"]
            stats["operator_credits"] += issue_stats["operator_credits"]
            stats["planned_credits"] += issue_stats["planned_credits"]
            stats["unplanned_credits"] += issue_stats["unplanned_credits"]
            stats["unknown_developer_associations"] += issue_stats["unknown_developer_associations"]
            for unknown_name in issue_stats.get("unknown_developer_names", []):
                name_text = str(unknown_name).strip()
                if name_text == "":
                    continue
                stats["unknown_developer_names"].add(name_text)

        upsert_operator_metrics_rows(
            conn,
            metric_year,
            metric_week_number,
            metric_date,
            week_start,
            week_end,
            synced_at,
            totals_by_operator,
        )
        upsert_operator_metric_task_rows(
            conn,
            metric_year,
            metric_week_number,
            week_start,
            week_end,
            synced_at,
            task_rows_by_operator,
        )

        summary = build_metrics_summary(conn, week_start=week_start)
        unknown_developer_names = sorted(list(stats["unknown_developer_names"]))
        return MetricsSyncResponse(
            summary=summary,
            stats=MetricsSyncStats(
                metricDate=metric_date,
                metricYear=metric_year,
                metricWeekNumber=metric_week_number,
                weekStart=week_start,
                weekEnd=week_end,
                syncedAt=synced_at,
                completedIssues=stats["completed_issues"],
                operatorCredits=stats["operator_credits"],
                plannedCredits=stats["planned_credits"],
                unplannedCredits=stats["unplanned_credits"],
                unknownDeveloperAssociations=stats["unknown_developer_associations"],
                unknownDeveloperNames=unknown_developer_names,
                operatorRowsUpdated=len(totals_by_operator),
                issuesScanned=stats["issues_scanned"],
            ),
        )
    finally:
        conn.close()


def metrics_tasks_response(
    conn: sqlite3.Connection,
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
) -> MetricsTasksResponse:
    operator_names = get_model_operator_names(conn)

    resolved_year, resolved_week_number, resolved_week_start, resolved_week_end = resolve_metrics_week(
        metric_year,
        metric_week_number,
        week_start,
    )
    task_rows_by_operator = get_operator_metric_task_rows(conn, resolved_year, resolved_week_number)

    operators_payload: List[OperatorMetricTasks] = []
    for operator_name in operator_names:
        tasks: List[OperatorMetricTask] = []
        rows = task_rows_by_operator.get(operator_name, [])
        for row in rows:
            tasks.append(
                OperatorMetricTask(
                    issueKey=str(row["issue_key"]),
                    description=str(row["issue_description"]) if row["issue_description"] is not None else None,
                    parentTask=str(row["parent_task"]) if row["parent_task"] is not None else None,
                    planned=bool(int(row["planned"])),
                )
            )
        operators_payload.append(
            OperatorMetricTasks(
                operatorName=operator_name,
                tasks=tasks,
            )
        )

    jira_root = ""
    jira_query = ""
    try:
        config = load_config()
        jira_root = jira_root_url(config)
        planned_board_names = get_planned_board_names(config)
        unplanned_board_names = get_unplanned_board_names(config)
        project_scope = planned_board_names + [name for name in unplanned_board_names if name not in planned_board_names]
        if len(operator_names) > 0 and len(project_scope) > 0:
            jira_query = build_weekly_done_jql(operator_names, project_scope, resolved_week_start, resolved_week_end)
    except HTTPException:
        jira_root = ""
        jira_query = ""

    return MetricsTasksResponse(
        metricYear=resolved_year,
        metricWeekNumber=resolved_week_number,
        weekStart=resolved_week_start,
        weekEnd=resolved_week_end,
        currentDate=local_today_iso(),
        jiraRootUrl=jira_root,
        jiraQuery=jira_query,
        operators=operators_payload,
    )


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
    )


@router.get("/sync-jira", response_model=JiraSyncResponse)
def sync_jira() -> JiraSyncResponse:
    started = time.monotonic()
    log.info("jira.sync.start")

    config = load_config()
    root_url = jira_root_url(config)
    headers = jira_headers(config)
    board_id = get_fr_board_id(config)
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


@router.get("/metrics", response_model=MetricsSummaryResponse)
def get_metrics(
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
) -> MetricsSummaryResponse:
    conn = get_model_db_connection()
    try:
        ensure_operator_metrics_table(conn)
        return build_metrics_summary(conn, metric_year, metric_week_number, week_start)
    finally:
        conn.close()


@router.get("/metrics-window", response_model=MetricsWindowResponse)
def get_metrics_window(week_start: str | None = None, window_size: int = 5) -> MetricsWindowResponse:
    conn = get_model_db_connection()
    try:
        ensure_operator_metrics_table(conn)
        return build_metrics_window(conn, week_start=week_start, window_size=window_size)
    finally:
        conn.close()


@router.get("/metrics-tasks", response_model=MetricsTasksResponse)
def get_metrics_tasks(
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
) -> MetricsTasksResponse:
    conn = get_model_db_connection()
    try:
        ensure_operator_metrics_table(conn)
        ensure_operator_metric_tasks_table(conn)
        return metrics_tasks_response(conn, metric_year, metric_week_number, week_start)
    finally:
        conn.close()


@router.post("/sync-task-metrics", response_model=MetricsSyncResponse)
def sync_task_metrics(
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
) -> MetricsSyncResponse:
    started = time.monotonic()
    log.info("metrics.sync.start")

    config = load_config()
    headers = jira_headers(config)
    response = sync_task_metrics_response(config, headers, metric_year, metric_week_number, week_start)

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "metrics.sync.done date=%s issues=%s credits=%s elapsed_ms=%s",
        response.stats.metricDate,
        response.stats.completedIssues,
        response.stats.operatorCredits,
        elapsed_ms,
    )
    return response


@router.get("/model", response_model=ModelResponse)
def get_model() -> ModelResponse:
    jira_root = ""
    try:
        config = load_config()
        jira_root = jira_root_url(config)
    except HTTPException:
        # Model load should still work even if Jira config is incomplete.
        jira_root = ""

    conn = get_model_db_connection()
    try:
        row = read_model_row(conn)
        if row is None:
            return ModelResponse(
                schemaVersion=CURRENT_MODEL_SCHEMA_VERSION,
                revision=0,
                state=default_visualizer_state(),
                config=ConfigResponse(jiraRootUrl=jira_root),
            )

        raw_schema_version = int(row["schema_version"])
        parsed_state = parse_model_state(str(row["state_json"]))
        migrated_state = upgrade_model_state(raw_schema_version, parsed_state)

        return ModelResponse(
            schemaVersion=CURRENT_MODEL_SCHEMA_VERSION,
            revision=int(row["revision"]),
            state=migrated_state,
            config=ConfigResponse(jiraRootUrl=jira_root),
        )
    finally:
        conn.close()


@router.put("/model", response_model=ModelResponse)
def put_model(body: SaveModelRequest) -> ModelResponse:
    conn = get_model_db_connection()
    try:
        return upsert_model_row(conn, body.state, body.revision)
    finally:
        conn.close()
