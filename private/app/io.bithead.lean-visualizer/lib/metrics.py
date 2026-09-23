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
    metric_rows = get_operator_metric_rows(
        conn,
        summary_year,
        summary_week_number
    )

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
        raise HTTPException(
            status_code=400,
            detail="window_size must be between 1 and 26"
        )

    current_week_start = current_week_start_iso()
    current_week_start_date = date.fromisoformat(current_week_start)
    current_week_end = (current_week_start_date + timedelta(days=6)).isoformat()

    if week_start is None:
        selected_week_start = current_week_start
    else:
        _, _, selected_week_start, _ = resolve_metrics_week(
            None,
            None,
            week_start=week_start
        )

    end_week_start_date = date.fromisoformat(selected_week_start)
    start_week_start_date = end_week_start_date - timedelta(days=(window_size - 1) * 7)

    weeks: List[MetricsSummaryResponse] = []
    for index in range(window_size):
        week_start_date = start_week_start_date + timedelta(days=index * 7)
        weeks.append(build_metrics_summary(
            conn,
            week_start=week_start_date.isoformat()
        ))

    return MetricsWindowResponse(
        windowSize=window_size,
        currentWeekStart=current_week_start,
        currentWeekEnd=current_week_end,
        weeks=weeks,
    )

def count_metrics_for_issue(
    issue: Dict[str, Any],
    developers_field_key: str,
    operator_totals: Dict[str, Dict[str, int]],
    task_rows_by_operator: Dict[str, Dict[str, OperatorMetricTask]] | None,
) -> Dict[str, int]:
    fields = issue.get(
        "fields",
        {}
    ) if isinstance(issue.get("fields", {}), dict) else {}
    issue_key = str(issue.get("key", "")).strip()
    issue_description = str(fields.get("summary", "")).strip() or None
    parent = fields.get("parent")
    is_unplanned = parent in (None, "")

    # `Developers` is the only source of attribution. An issue with several
    # developers credits each of them. Assignee is never consulted: it names who
    # owns the ticket, not who did the work.
    people = extract_people(fields.get(developers_field_key))

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
            fix_version_names = extract_release_version_from_fix_versions(fields.get("fixVersions"))
            task_rows_by_operator[person_name][issue_key] = OperatorMetricTask(
                issueKey=issue_key,
                description=issue_description,
                parentTask=parent_task_label(fields),
                planned=not is_unplanned,
                releaseVersion=fix_version_names,
            )
        matched_people += 1

    if matched_people == 0 and len(people) == 0:
        unknown_people = 1
        unknown_developer_names.append(f"No {DEVELOPERS_FIELD_NAME} set")

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
        raise HTTPException(
            status_code=500,
            detail="config.json does not define planned_board_names or unplanned_board_names"
        )

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

        metric_year, metric_week_number, week_start, week_end = resolve_metrics_week(
            metric_year,
            metric_week_number,
            week_start
        )
        metric_date = local_today_iso()
        synced_at = local_now().isoformat(timespec="seconds")
        jql = ""
        issues: List[Dict[str, Any]] = []
        developers_field_id = get_developers_field_id(config, headers)

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
            jql = build_weekly_done_jql(
                operator_names,
                project_scope,
                week_start,
                week_end
            )
            issues = fetch_weekly_done_issues(
                root_url,
                headers,
                jql,
                developers_field_id
            )

        for issue in issues:
            stats["issues_scanned"] += 1
            issue_stats = count_metrics_for_issue(
                issue,
                developers_field_id,
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
    task_rows_by_operator = get_operator_metric_task_rows(
        conn,
        resolved_year,
        resolved_week_number
    )

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
            jira_query = build_weekly_done_jql(
                operator_names,
                project_scope,
                resolved_week_start,
                resolved_week_end
            )
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

def issue_completed_week_label(issue: Dict[str, Any]) -> str:
    changelog = issue.get("changelog")
    if not isinstance(changelog, dict):
        return "—"

    completed_at: datetime | None = None
    histories = changelog.get("histories", [])
    if not isinstance(histories, list):
        histories = []

    for history in histories:
        if not isinstance(history, dict):
            continue
        created = parse_jira_datetime(history.get("created"))
        if created is None:
            continue
        items = history.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("field", "")).strip().lower() != "status":
                continue
            to_status = str(item.get("toString", "")).strip().lower()
            if to_status not in COMPLETED_STATUSES:
                continue
            if completed_at is None or created > completed_at:
                completed_at = created

    if completed_at is None:
        return "—"

    week_start, week_end = week_bounds_for_date(completed_at.astimezone().date())
    return f"{week_start} -- {week_end}"
