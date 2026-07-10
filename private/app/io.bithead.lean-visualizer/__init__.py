"""Lean Visualizer private API."""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/io.bithead.lean-visualizer")

PRIVATE_CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
COMPLETED_STATUSES = {"done", "won't do", "won’t do", "duplicate"}


def start() -> None:
    logging.info("Starting Lean Visualizer...")


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
