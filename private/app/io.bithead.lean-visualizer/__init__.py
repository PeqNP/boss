"""Lean Visualizer private API."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from lib.model import User
from lib.server import require_acl, verify_user

from .db import start, shutdown, get_model_db_connection
from .lib import *
from .model import *

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/io.bithead.lean-visualizer")


@router.get("/sync-jira", response_model=JiraSyncResponse)
@require_acl("board.w", roles=[Role.ADMIN])
async def sync_jira(boss_user: User, request: Request) -> JiraSyncResponse:
    started = time.monotonic()
    log.info("jira.sync.start")

    config = load_config()
    root_url = jira_root_url(config)
    headers = jira_headers(config)
    board_id = get_fr_board_id(config)
    pillar_field_id = get_custom_field_id(
        config,
        headers,
        STRATEGIC_PILLAR_FIELD_NAME,
    )
    board_query = urlencode(
        {
            "fields": "summary,issuetype,status,assignee,fixVersions,updated," + pillar_field_id,
            "jql": "issuetype = Epic AND statusCategory != Done ORDER BY Rank ASC",
        }
    )
    board_url = f"{root_url}/rest/agile/1.0/board/{board_id}/issue?{board_query}"
    log.info(
        "jira.sync.board_fetch_start board_id=%s url=%s",
        board_id,
        board_url
    )
    issues = fetch_all_issues(board_url, headers)
    log.info(
        "jira.sync.board_fetch_done board_id=%s issues=%s",
        board_id,
        len(issues)
    )

    conn = get_model_db_connection()
    try:
        ensure_model_table(conn)
        row = read_model_row(conn)
        if row is None:
            state = default_visualizer_state()
        else:
            schema_version = int(row["schema_version"])
            parsed_state = parse_model_state(str(row["state_json"]))
            state = upgrade_model_state(schema_version, parsed_state)

        backlog = state.get("backlog")
        if not isinstance(backlog, list):
            backlog = []
            state["backlog"] = backlog
        ensure_system_sync_divider(backlog)

        backlog_above_divider_issue_keys = collect_backlog_issue_keys_above_divider(backlog)
        track_issue_keys = collect_track_issue_keys(state.get("tracks"))
        count_refresh_issue_keys = backlog_above_divider_issue_keys | track_issue_keys

        work_units: List[JiraWorkUnit] = []
        processed_epics = 0
        for issue in issues:
            issue_key = normalize_issue_key(issue.get("key"))
            include_counts = bool(issue_key is not None and issue_key in count_refresh_issue_keys)
            work_unit = to_work_unit(
                issue,
                headers,
                root_url,
                include_counts,
                pillar_field_id,
            )
            if work_unit is None:
                continue
            work_units.append(work_unit)
            processed_epics += 1

        updated_state, sync_stats = apply_jira_sync_to_state(state, work_units)
        store_pillars(conn, [
            {"issueKey": unit.issueKey, "pillars": unit.pillars}
            for unit in work_units
        ])

        virtual_updated = sync_virtual_features(
            updated_state,
            headers,
            root_url
        )
        log.info("jira.sync.virtual_features updated=%s", virtual_updated)

        upsert_model_row(conn, updated_state, None)
        log.info(
            "jira.sync.state_update new=%s updated=%s removed=%s",
            sync_stats["new_count"],
            sync_stats["updated_count"],
            sync_stats["removed_count"],
        )
    finally:
        conn.close()

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "jira.sync.done board_id=%s epics=%s elapsed_ms=%s",
        board_id,
        processed_epics,
        elapsed_ms
    )

    return JiraSyncResponse(
        boardId=board_id,
        jiraRootUrl=root_url,
        issues=work_units,
        virtualFeaturesUpdated=virtual_updated,
    )


@router.get("/metrics", response_model=MetricsSummaryResponse)
@require_acl("board.r", roles=[Role.ADMIN])
async def get_metrics(
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
    boss_user: User = None,
    request: Request = None,
) -> MetricsSummaryResponse:
    conn = get_model_db_connection()
    try:
        ensure_operator_metrics_table(conn)
        return build_metrics_summary(
            conn,
            metric_year,
            metric_week_number,
            week_start
        )
    finally:
        conn.close()


@router.get("/metrics-window", response_model=MetricsWindowResponse)
@require_acl("report.r", roles=[Role.ADMIN, Role.EMPLOYEE])
async def get_metrics_window(
    week_start: str | None = None,
    window_size: int = 5,
    boss_user: User = None,
    request: Request = None,
) -> MetricsWindowResponse:
    conn = get_model_db_connection()
    try:
        ensure_operator_metrics_table(conn)
        return build_metrics_window(
            conn,
            week_start=week_start,
            window_size=window_size
        )
    finally:
        conn.close()


@router.get("/metrics-tasks", response_model=MetricsTasksResponse)
@require_acl("board.r", roles=[Role.ADMIN])
async def get_metrics_tasks(
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
    boss_user: User = None,
    request: Request = None,
) -> MetricsTasksResponse:
    conn = get_model_db_connection()
    try:
        ensure_operator_metrics_table(conn)
        ensure_operator_metric_tasks_table(conn)
        return metrics_tasks_response(
            conn,
            metric_year,
            metric_week_number,
            week_start
        )
    finally:
        conn.close()


@router.post("/sync-task-metrics", response_model=MetricsSyncResponse)
@require_acl("board.w", roles=[Role.ADMIN])
async def sync_task_metrics(
    metric_year: int | None = None,
    metric_week_number: int | None = None,
    week_start: str | None = None,
    boss_user: User = None,
    request: Request = None,
) -> MetricsSyncResponse:
    started = time.monotonic()
    log.info("metrics.sync.start")

    config = load_config()
    headers = jira_headers(config)
    response = sync_task_metrics_response(
        config,
        headers,
        metric_year,
        metric_week_number,
        week_start
    )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "metrics.sync.done date=%s issues=%s credits=%s elapsed_ms=%s",
        response.stats.metricDate,
        response.stats.completedIssues,
        response.stats.operatorCredits,
        elapsed_ms,
    )
    return response


@router.get("/finished-work", response_model=FinishedWorkResponse)
@require_acl("report.r", roles=[Role.ADMIN, Role.EMPLOYEE])
async def get_finished_work(
    year: int,
    operator_name: str = "",
    boss_user: User = None,
    request: Request = None,
) -> FinishedWorkResponse:
    if year < 2026:
        raise HTTPException(
            status_code=400,
            detail="year must be 2026 or greater"
        )

    config = load_config()
    root_url = jira_root_url(config)
    headers = jira_headers(config)
    board_id = get_fr_board_id(config)

    start_jira = f"{year:04d}/01/01"
    end_jira = f"{year:04d}/12/31"
    operator_name_clean = str(operator_name or "").strip()

    done_jql = (
        "issuetype = Epic "
        "AND statusCategory = Done "
        f'AND status CHANGED TO Done DURING ("{start_jira}", "{end_jira}") '
        "ORDER BY updated DESC"
    )

    board_query = urlencode(
        {
            "fields": "summary,issuetype,status,assignee,updated",
            "jql": done_jql,
            "expand": "changelog",
        }
    )
    board_url = f"{root_url}/rest/agile/1.0/board/{board_id}/issue?{board_query}"
    issues = fetch_all_issues(board_url, headers)

    items: List[FinishedWorkItem] = []
    for issue in issues:
        issue_key = normalize_issue_key(issue.get("key"))
        if issue_key is None:
            continue

        issue_fields = issue.get(
            "fields",
            {}
        ) if isinstance(issue.get("fields"), dict) else {}
        summary = str(issue_fields.get("summary", "")).strip() or issue_key
        assignee_candidates = extract_people(issue_fields.get("assignee"))
        operator_label = assignee_candidates[0] if len(assignee_candidates) > 0 else "Unassigned"
        if operator_name_clean != "":
            if operator_name_clean.lower() == "unassigned" and operator_label != "Unassigned":
                continue
            if operator_name_clean.lower() != "unassigned" and operator_label != operator_name_clean:
                continue

        completed_week = issue_completed_week_label(issue)
        items.append(
            FinishedWorkItem(
                issueKey=issue_key,
                description=summary,
                completedWeek=completed_week,
                operatorName=operator_label,
            )
        )

    return FinishedWorkResponse(
        jiraRootUrl=root_url,
        year=year,
        operatorName=operator_name_clean,
        items=items,
    )


@router.get("/model", response_model=ModelResponse)
@require_acl("board.r", roles=[Role.ADMIN])
async def get_model(boss_user: User, request: Request) -> ModelResponse:
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
@require_acl("board.w", roles=[Role.ADMIN])
async def put_model(body: SaveModelRequest, boss_user: User, request: Request) -> ModelResponse:
    conn = get_model_db_connection()
    try:
        return upsert_model_row(conn, body.state, body.revision)
    finally:
        conn.close()


@router.get("/me", response_model=Me)
@require_acl("report.r", roles=[Role.ADMIN, Role.EMPLOYEE])
async def get_me(boss_user: User, request: Request) -> Me:
    role = Role.EMPLOYEE.value
    try:
        await verify_user(request, __name__, "board.w")
        role = Role.ADMIN.value
    except HTTPException:
        role = Role.EMPLOYEE.value
    return Me(role=role)


@router.get("/schedule", response_model=ScheduleResponse)
@require_acl("schedule.r", roles=[Role.ADMIN, Role.EMPLOYEE])
async def get_schedule(boss_user: User, request: Request) -> ScheduleResponse:
    conn = get_model_db_connection()
    try:
        return build_schedule(conn)
    finally:
        conn.close()


@router.get("/report", response_model=ReportResponse)
@require_acl("report.r", roles=[Role.ADMIN, Role.EMPLOYEE])
async def get_report(boss_user: User, request: Request) -> ReportResponse:
    conn = get_model_db_connection()
    try:
        return build_report(conn)
    finally:
        conn.close()


@router.put("/checkpoints/{release_id}", response_model=CheckpointResponse)
@require_acl("checkpoint.w", roles=[Role.ADMIN])
async def put_checkpoint(release_id: str, boss_user: User, request: Request) -> CheckpointResponse:
    conn = get_model_db_connection()
    try:
        state = read_board_state(conn)
        _release, window_start, window_end = checkpoint_window(state, release_id)
        names = [
            str(item.get("name") or "").strip()
            for item in state.get("operators") or []
            if isinstance(item, dict) and str(item.get("name") or "").strip() != ""
        ]
        issues: List[Dict[str, Any]] = []
        field = "developers"
        if len(names) > 0:
            issues, field = fetch_checkpoint_issues(names, window_start, window_end)
        return save_checkpoint(
            conn,
            release_id,
            issues,
            developers_field=field,
            trust_window=True,
        )
    finally:
        conn.close()
