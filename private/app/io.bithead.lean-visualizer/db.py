"""Lean Visualizer database."""

import logging
import os
import sqlite3
import sys
from datetime import date, datetime
from typing import Any, Dict, List

from lib import get_config

from .model import *

MODEL_ID = "default"
CURRENT_MODEL_SCHEMA_VERSION = 1


MODEL_DB_NAME = "lean-visualizer.sqlite3"

def get_db_version(conn: sqlite3.Connection) -> tuple | None:
    try:
        cursor = conn.execute(
            "SELECT version FROM versions ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
    except Exception:
        return None
    if not row:
        return None
    return tuple(int(v) for v in row[0].split("."))

def migrate_to_1_0_0(conn: sqlite3.Connection, version: tuple | None) -> tuple:
    if version is not None:
        return version

    logging.info("Lean Visualizer: applying db migration v1.0.0")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
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
            release_version TEXT NOT NULL DEFAULT '',
            synced_at TEXT NOT NULL,
            UNIQUE(operator_name, metric_year, metric_week_number, issue_key)
        )
        """
    )
    # Check if release_version column exists (for tables created before it was added)
    cursor = conn.execute(
        "PRAGMA table_info(visualizer_operator_metric_tasks)"
    )
    columns = {row[1] for row in cursor.fetchall()}
    if "release_version" not in columns:
        conn.execute(
            "ALTER TABLE visualizer_operator_metric_tasks ADD COLUMN release_version TEXT NOT NULL DEFAULT ''"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visualizer_operator_metric_tasks_year_week ON visualizer_operator_metric_tasks(metric_year, metric_week_number)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visualizer_operator_metric_tasks_operator_year_week ON visualizer_operator_metric_tasks(operator_name, metric_year, metric_week_number)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visualizer_operator_metric_tasks_release_version ON visualizer_operator_metric_tasks(release_version)"
    )
    conn.execute(
        "INSERT INTO versions (version, created_at) VALUES (?, datetime('now'))",
        ("1.0.0",),
    )
    conn.commit()
    return (1, 0, 0)

def start() -> None:
    logging.info("Starting Lean Visualizer...")
    cfg = get_config()
    os.makedirs(cfg.db_path, exist_ok=True)
    conn = get_model_db_connection()
    try:
        ver = get_db_version(conn)
        logging.info("Lean Visualizer: db version (%s)", ver)
        ver = migrate_to_1_0_0(conn, ver)
    finally:
        conn.close()

def shutdown() -> None:
    pass

def get_model_db_connection() -> sqlite3.Connection:
    cfg = get_config()
    app = sys.modules.get(__package__ or "")
    name = getattr(app, "MODEL_DB_NAME", MODEL_DB_NAME)
    path = os.path.join(cfg.db_path, name)
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
            release_version TEXT NOT NULL DEFAULT '',
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visualizer_operator_metric_tasks_release_version ON visualizer_operator_metric_tasks(release_version)"
    )
    conn.commit()

def read_model_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    cursor = conn.execute(
        "SELECT id, schema_version, state_json, revision, updated_at FROM visualizer_models WHERE id = ?",
        (MODEL_ID,),
    )
    return cursor.fetchone()

def get_model_operator_names(conn: sqlite3.Connection) -> List[str]:
    row = read_model_row(conn)
    if row is None:
        return []

    from .lib.board import parse_model_state
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

def get_operator_metric_rows(
    conn: sqlite3.Connection,
    metric_year: int,
    metric_week_number: int
) -> Dict[str, sqlite3.Row]:
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

def get_operator_metric_task_rows(
    conn: sqlite3.Connection,
    metric_year: int,
    metric_week_number: int
) -> Dict[str, List[sqlite3.Row]]:
    cursor = conn.execute(
        """
        SELECT operator_name,
               issue_key,
               issue_description,
               parent_task,
               planned,
               release_version
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
                    release_version,
                    synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    task.releaseVersion,
                    synced_at,
                ),
            )
    conn.commit()

def ensure_feature_pillars(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_pillars (
            issue_key TEXT PRIMARY KEY,
            pillars_json TEXT NOT NULL,
            synced_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

def ensure_checkpoint_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            release_id TEXT NOT NULL,
            release_version TEXT NOT NULL,
            release_date TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            rate_json TEXT NOT NULL,
            UNIQUE(release_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkpoint_id INTEGER NOT NULL,
            operator_name TEXT NOT NULL,
            issue_key TEXT NOT NULL,
            issue_description TEXT,
            parent_task TEXT,
            planned INTEGER NOT NULL,
            UNIQUE(checkpoint_id, operator_name, issue_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkpoint_id INTEGER NOT NULL,
            feature_id TEXT NOT NULL,
            issue_key TEXT,
            name TEXT NOT NULL,
            color TEXT NOT NULL,
            track_id TEXT,
            track_name TEXT,
            finish_on TEXT,
            finish_weeks REAL,
            remaining_units INTEGER NOT NULL,
            manual_est_weeks REAL NOT NULL DEFAULT 0,
            UNIQUE(checkpoint_id, feature_id)
        )
        """
    )
    conn.commit()

def write_model_row(
    conn: sqlite3.Connection,
    model_id: str,
    schema_version: int,
    state_json: str,
    revision: int,
) -> None:
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
        (model_id, schema_version, state_json, revision),
    )

def replace_operator_metric_week(
    conn: sqlite3.Connection,
    operator_name: str,
    metric_year: int,
    metric_week_number: int,
    metric_date: str,
    week_start: str,
    week_end: str,
    synced_at: str,
    units_week: int,
    unplanned_work_week: int,
) -> None:
    conn.execute(
        """
        DELETE FROM visualizer_operator_metrics
        WHERE operator_name = ? AND metric_year = ? AND metric_week_number = ?
        """,
        (operator_name, metric_year, metric_week_number),
    )
    conn.execute(
        """
        INSERT INTO visualizer_operator_metrics (
            operator_name, metric_year, metric_week_number, metric_date,
            week_start, week_end, synced_at, units_week, unplanned_work_week
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            operator_name,
            metric_year,
            metric_week_number,
            metric_date,
            week_start,
            week_end,
            synced_at,
            units_week,
            unplanned_work_week,
        ),
    )

def operator_weeks_since(
    conn: sqlite3.Connection,
    earliest: str,
) -> List[sqlite3.Row]:
    return conn.execute(
        """
        SELECT operator_name, week_start, week_end, units_week, unplanned_work_week
        FROM visualizer_operator_metrics
        WHERE week_start >= ?
        ORDER BY week_start, operator_name
        """,
        (earliest,),
    ).fetchall()

def upsert_feature_pillar(
    conn: sqlite3.Connection,
    issue_key: str,
    pillars_json: str,
    synced_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO feature_pillars (issue_key, pillars_json, synced_at)
        VALUES (?, ?, ?)
        ON CONFLICT(issue_key) DO UPDATE SET
            pillars_json = excluded.pillars_json,
            synced_at = excluded.synced_at
        """,
        (issue_key, pillars_json, synced_at),
    )

def feature_pillar_rows(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT issue_key, pillars_json FROM feature_pillars"
    ).fetchall()

def latest_checkpoint_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id FROM checkpoints ORDER BY release_date DESC, id DESC LIMIT 1"
    ).fetchone()

def checkpoint_forecast_rows(
    conn: sqlite3.Connection,
    checkpoint_id: int,
) -> List[sqlite3.Row]:
    return conn.execute(
        """
        SELECT feature_id, name, color, finish_on
        FROM checkpoint_forecasts
        WHERE checkpoint_id = ?
        """,
        (checkpoint_id,),
    ).fetchall()

def insert_checkpoint_issue(
    conn: sqlite3.Connection,
    checkpoint_id: int,
    operator_name: str,
    issue_key: str,
    issue_description: str | None,
    parent_task: str | None,
    planned: int,
) -> None:
    conn.execute(
        """
        INSERT INTO checkpoint_issues (
            checkpoint_id, operator_name, issue_key, issue_description,
            parent_task, planned
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            checkpoint_id,
            operator_name,
            issue_key,
            issue_description,
            parent_task,
            planned,
        ),
    )

def checkpoint_issue_rows(
    conn: sqlite3.Connection,
    release_id: str,
) -> List[sqlite3.Row]:
    return conn.execute(
        """
        SELECT operator_name, issue_key, planned
        FROM checkpoint_issues
        JOIN checkpoints ON checkpoints.id = checkpoint_issues.checkpoint_id
        WHERE checkpoints.release_id = ?
        ORDER BY issue_key, operator_name
        """,
        (release_id,),
    ).fetchall()

def delete_checkpoint_for_release(
    conn: sqlite3.Connection,
    release_id: str,
) -> None:
    conn.execute(
        """
        DELETE FROM checkpoint_issues
        WHERE checkpoint_id IN (
            SELECT id FROM checkpoints WHERE release_id = ?
        )
        """,
        (release_id,),
    )
    conn.execute(
        """
        DELETE FROM checkpoint_forecasts
        WHERE checkpoint_id IN (
            SELECT id FROM checkpoints WHERE release_id = ?
        )
        """,
        (release_id,),
    )
    conn.execute(
        "DELETE FROM checkpoints WHERE release_id = ?",
        (release_id,),
    )

def insert_checkpoint(
    conn: sqlite3.Connection,
    release_id: str,
    release_version: str,
    release_date: str,
    window_start: str,
    window_end: str,
    saved_at: str,
    rate_json: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO checkpoints (
            release_id, release_version, release_date, window_start,
            window_end, saved_at, rate_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            release_id,
            release_version,
            release_date,
            window_start,
            window_end,
            saved_at,
            rate_json,
        ),
    )
    return int(cursor.lastrowid)

def insert_checkpoint_forecast(
    conn: sqlite3.Connection,
    checkpoint_id: int,
    feature_id: str,
    name: str,
    color: str,
    track_id: str,
    track_name: str,
    finish_on: str,
) -> None:
    conn.execute(
        """
        INSERT INTO checkpoint_forecasts (
            checkpoint_id, feature_id, name, color, track_id, track_name,
            finish_on, remaining_units, manual_est_weeks
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        """,
        (
            checkpoint_id,
            feature_id,
            name,
            color,
            track_id,
            track_name,
            finish_on,
        ),
    )
