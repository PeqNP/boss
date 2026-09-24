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


log = logging.getLogger(__name__)

PRIVATE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"

COMPLETED_STATUSES = {
    "done",
    "deployed - prod",
    "released to public",
    "won't do",
    "duplicate",
}

COMPLETED_TRANSITION_STATUSES = COMPLETED_STATUSES

DEVELOPERS_FIELD_NAME = "Developers"

DEVELOPERS_JQL_NAME = "Developers[User Picker (multiple users)]"

SEMVER_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

DEVELOPERS_FIELD_ID = None

def next_jira_feature_color() -> str:
    hue = random.randint(0, 359)
    sat = 62 + random.randint(0, 17)
    light = 56 + random.randint(0, 9)
    return f"hsl({hue} {sat}% {light}%)"

def clamp_units(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if not isinstance(value, (int, float)):
        return 0
    return max(0, int(value))

def apply_jira_sync_to_state(
    state: Dict[str, Any],
    work_units: List[JiraWorkUnit]
) -> tuple[Dict[str, Any], Dict[str, int]]:
    tracks = state.get("tracks")
    backlog = state.get("backlog")
    if not isinstance(tracks, list):
        tracks = []
        state["tracks"] = tracks
    if not isinstance(backlog, list):
        backlog = []
        state["backlog"] = backlog

    def feature_issue_key(feature: Any) -> str | None:
        if not isinstance(feature, dict):
            return None
        return normalize_issue_key(feature.get("issueKey") or feature.get("id"))

    def is_feature_item(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        kind = str(item.get("kind", "feature")).strip()
        return kind not in ("divider", SYSTEM_DIVIDER_KIND)

    ensure_system_sync_divider(backlog)
    divider_index = system_divider_index(backlog)

    all_features: List[Dict[str, Any]] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        feature = track.get("feature")
        if is_feature_item(feature):
            all_features.append(feature)
    for item in backlog:
        if is_feature_item(item):
            all_features.append(item)

    by_issue_key: Dict[str, List[Dict[str, Any]]] = {}
    for feature in all_features:
        issue_key = feature_issue_key(feature)
        if issue_key is None:
            continue
        if issue_key not in by_issue_key:
            by_issue_key[issue_key] = []
        by_issue_key[issue_key].append(feature)

    active_issue_keys: set[str] = set()
    new_count = 0
    updated_count = 0
    removed_count = 0

    for work_unit in work_units:
        issue_key = normalize_issue_key(work_unit.issueKey)
        if issue_key is None:
            continue

        counts_fresh = bool(work_unit.countsFresh)
        active_issue_keys.add(issue_key)

        units = clamp_units(work_unit.totalUnits)
        completed_units = min(units, clamp_units(work_unit.completedUnits))
        issue_type = str(work_unit.issueType or "").strip()
        summary = str(work_unit.name or issue_key).strip() or issue_key
        release_version = str(work_unit.releaseVersion or "").strip()

        existing_features = by_issue_key.get(issue_key, [])
        if len(existing_features) == 0:
            new_feature = {
                "kind": "feature",
                "id": issue_key,
                "issueKey": issue_key,
                "name": summary,
                "units": units if counts_fresh else 0,
                "completedUnits": completed_units if counts_fresh else 0,
                "manualEstWeeks": 0,
                "done": False,
                "releaseVersion": release_version,
                "pinnedTrackId": None,
                "color": next_jira_feature_color(),
                "jiraIssueType": issue_type,
            }
            insert_index = len(backlog)
            if divider_index is not None:
                insert_index = min(len(backlog), divider_index + 1)
            backlog.insert(insert_index, new_feature)
            if divider_index is not None and insert_index <= divider_index:
                divider_index += 1
            by_issue_key[issue_key] = [new_feature]
            new_count += 1
            continue

        for feature in existing_features:
            changed = False
            if feature.get("issueKey") != issue_key:
                feature["issueKey"] = issue_key
                changed = True
            if feature.get("id") in (None, ""):
                feature["id"] = issue_key
                changed = True
            if str(feature.get("name", "")).strip() != summary:
                feature["name"] = summary
                changed = True
            if counts_fresh:
                if clamp_units(feature.get("units")) != units:
                    feature["units"] = units
                    changed = True
                if clamp_units(feature.get("completedUnits")) != completed_units:
                    feature["completedUnits"] = completed_units
                    changed = True
            if "assignee" in feature:
                del feature["assignee"]
                changed = True
            if str(feature.get(
                "releaseVersion",
                ""
            )).strip() != release_version:
                feature["releaseVersion"] = release_version
                changed = True
            if str(feature.get("jiraIssueType", "")).strip() != issue_type:
                feature["jiraIssueType"] = issue_type
                changed = True
            if changed:
                updated_count += 1

    # A synced FR is one whose Jira project this sync just read. Membership is
    # derived from what Jira returned rather than from a field on the feature:
    # `jiraIssueType` does not survive a round trip through the client, so a
    # feature that has been saved even once no longer carries it.
    synced_projects = {issue_key_project(key) for key in active_issue_keys}

    def is_retired_feature(feature: Any, issue_key: str) -> bool:
        """ True when Jira no longer lists this FR as open. """
        if issue_key in active_issue_keys:
            return False
        if str(feature.get("jiraIssueType", "")).strip().lower() == "epic":
            return True
        return issue_key_project(issue_key) in synced_projects

    # Remove FRs that are no longer returned by Jira open-epic sync. An empty
    # result means the fetch found nothing to compare against; removing on that
    # basis would empty the board.
    if len(active_issue_keys) > 0:
        for track in tracks:
            if not isinstance(track, dict):
                continue
            feature = track.get("feature")
            if not is_feature_item(feature):
                continue
            issue_key = feature_issue_key(feature)
            if issue_key is None:
                continue
            if not is_retired_feature(feature, issue_key):
                continue
            log.info("jira.sync.retired key=%s location=track", issue_key)
            track["feature"] = None
            removed_count += 1

        next_backlog: List[Any] = []
        for item in backlog:
            if not is_feature_item(item):
                next_backlog.append(item)
                continue
            issue_key = feature_issue_key(item)
            if issue_key is None:
                next_backlog.append(item)
                continue
            if not is_retired_feature(item, issue_key):
                next_backlog.append(item)
                continue
            log.info("jira.sync.retired key=%s location=backlog", issue_key)
            removed_count += 1
        state["backlog"] = next_backlog

    return state, {
        "new_count": new_count,
        "updated_count": updated_count,
        "removed_count": removed_count,
    }

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
    raise HTTPException(
        status_code=500,
        detail="config.json is missing fr_board_id"
    )

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
        raise HTTPException(
            status_code=500,
            detail="config.json does not define planned_board_names or unplanned_board_names"
        )

    if len(operator_names) == 0:
        raise HTTPException(
            status_code=400,
            detail="No operators are defined in the model"
        )

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
        f"AND \"{DEVELOPERS_JQL_NAME}\" IN ({operator_clause}) "
        "AND status IN (Done, \"Won't Do\") "
        f"AND status CHANGED TO (Done, \"Won't Do\") DURING (\"{start_jira}\", \"{end_jira}\") "
        "ORDER BY created DESC"
    )

def load_config() -> Dict[str, Any]:
    if not PRIVATE_CONFIG_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Missing config.json for io.bithead.lean-visualizer"
        )

    try:
        config = json.loads(PRIVATE_CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid config.json: {exc}"
        ) from exc

    required = ("jira_url", "account_email", "api_key")
    for key in required:
        if key not in config or config[key] in (None, ""):
            raise HTTPException(
                status_code=500,
                detail=f"config.json is missing {key}"
            )

    return config

def jira_headers(config: Dict[str, Any]) -> Dict[str, str]:
    token = base64.b64encode(f"{config['account_email']}:{config['api_key']}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    }

def jira_root_url(config: Dict[str, Any]) -> str:
    return str(config["jira_url"]).rstrip("/")

def get_jira_field_map(
    config: Dict[str, Any],
    headers: Dict[str, str]
) -> Dict[str, str]:
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

def get_developers_field_id(
    config: Dict[str, Any],
    headers: Dict[str, str]
) -> str:
    """ Resolve the custom field ID for `Developers`.

    The REST `fields` query parameter only honors field IDs. Asking for a custom
    field by its display name returns no error and no field, which is how task
    metrics silently fell back to `assignee`.
    """
    global DEVELOPERS_FIELD_ID
    if DEVELOPERS_FIELD_ID is not None:
        return DEVELOPERS_FIELD_ID

    field_map = get_jira_field_map(config, headers)
    field_id = field_map.get(DEVELOPERS_FIELD_NAME)
    if not field_id:
        raise HTTPException(
            status_code=502,
            detail=f"Jira has no field named ({DEVELOPERS_FIELD_NAME}). Task metrics cannot be attributed."
        )

    log.info("jira.field.developers id=%s", field_id)
    DEVELOPERS_FIELD_ID = field_id
    return field_id

def fetch_board_candidate_issues(
    board_id: int,
    headers: Dict[str, str],
    root_url: str,
    week_start: str,
    week_end: str
) -> List[Dict[str, Any]]:
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

def fetch_issue_details(
    issue_key: str,
    headers: Dict[str, str],
    root_url: str,
    field_ids: List[str]
) -> Dict[str, Any]:
    fields = ["summary", "status", "assignee", "parent", "updated"] + field_ids
    field_query = ",".join(fields)
    issue_url = f"{root_url}/rest/api/3/issue/{quote(issue_key)}?fields={quote(field_query)}&expand=changelog"
    return fetch_json(issue_url, headers)

def fetch_weekly_done_issues(
    root_url: str,
    headers: Dict[str, str],
    jql: str,
    developers_field_id: str,
) -> List[Dict[str, Any]]:
    query = urlencode(
        {
            "jql": jql,
            "maxResults": "1000",
            "fields": f"key,summary,status,parent,project,updated,fixVersions,{developers_field_id}",
        }
    )
    url = f"{root_url}/rest/api/3/search/jql?{query}"
    payload = fetch_json(url, headers)
    issues = payload.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    return issues

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

def issue_completed_in_range(
    issue: Dict[str, Any],
    start_date: date,
    end_date: date
) -> bool:
    changelog = issue.get("changelog", {})
    histories = changelog.get(
        "histories",
        []
    ) if isinstance(changelog, dict) else []
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

def _live_fetch_json(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    started = time.monotonic()
    log.info("jira.fetch.start url=%s", url)

    request = UrlRequest(url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.error(
            "jira.fetch.http_error url=%s status=%s elapsed_ms=%s",
            url,
            exc.code,
            elapsed_ms
        )
        detail = exc.read().decode(
            "utf-8",
            errors="ignore"
        ) if exc.fp else exc.reason
        raise HTTPException(
            status_code=exc.code,
            detail=f"Jira request failed for {url}: {detail}"
        ) from exc
    except URLError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.error(
            "jira.fetch.network_error url=%s elapsed_ms=%s reason=%s",
            url,
            elapsed_ms,
            exc.reason
        )
        raise HTTPException(
            status_code=502,
            detail=f"Jira request failed for {url}: {exc.reason}"
        ) from exc

    try:
        body = json.loads(payload)
    except json.JSONDecodeError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.error(
            "jira.fetch.invalid_json url=%s elapsed_ms=%s",
            url,
            elapsed_ms
        )
        raise HTTPException(
            status_code=502,
            detail=f"Jira returned invalid JSON for {url}"
        ) from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "jira.fetch.done url=%s elapsed_ms=%s bytes=%s",
        url,
        elapsed_ms,
        len(payload)
    )
    return body

class LiveJira:
    def fetch_json(self, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return _live_fetch_json(url, headers)

class FixtureJira:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def fetch_json(self, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return self.payload

_jira = LiveJira()

def fetch_json(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    return _jira.fetch_json(url, headers)

def use_fixture_jira(payload: Dict[str, Any]) -> None:
    global _jira
    _jira = FixtureJira(payload)

_FIXTURE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

def use_jira_fixture(name: str) -> None:
    if _FIXTURE_NAME.match(name) is None:
        raise HTTPException(status_code=400, detail="Invalid fixture name.")
    path = Path(__file__).resolve().parents[1] / "fixtures" / f"{name}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"No Jira fixture named ({name}).")
    use_fixture_jira(json.loads(path.read_text()))

def use_live_jira() -> None:
    global _jira
    _jira = LiveJira()

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
    log.info(
        "jira.issues.done url=%s pages=%s total_issues=%s elapsed_ms=%s",
        url,
        page_count,
        len(issues),
        elapsed_ms
    )
    return issues

def is_completed_status(status_name: str) -> bool:
    normalized = str(status_name or "").strip().lower()
    return normalized in COMPLETED_STATUSES

def extract_release_version_from_fix_versions(raw_fix_versions: Any) -> str:
    if not isinstance(raw_fix_versions, list):
        return ""

    version_matches: List[str] = []
    for raw_fix_version in raw_fix_versions:
        if not isinstance(raw_fix_version, dict):
            continue
        version_name = str(raw_fix_version.get("name", "")).strip()
        if SEMVER_PATTERN.match(version_name) is None:
            continue
        version_matches.append(version_name)

    if len(version_matches) == 1:
        return version_matches[0]
    return ""

def to_work_unit(
    issue: Dict[str, Any],
    headers: Dict[str, str],
    root_url: str,
    include_counts: bool
) -> JiraWorkUnit | None:
    started = time.monotonic()
    fields = issue.get("fields", {})
    issue_key = str(issue.get("key", "")).strip()
    if issue_key == "":
        return None

    issue_type = str(fields.get("issuetype", {}).get("name", ""))
    if issue_type.lower() != "epic":
        return None

    release_version = extract_release_version_from_fix_versions(fields.get("fixVersions"))

    summary = str(fields.get("summary", issue_key)).strip() or issue_key
    total_units = 0
    completed_units = 0
    if include_counts:
        child_url = f"{root_url}/rest/agile/1.0/epic/{quote(issue_key)}/issue?fields=status"
        child_issues = fetch_all_issues(child_url, headers)
        total_units = len(child_issues)
        for child in child_issues:
            child_status = child.get(
                "fields",
                {}
            ).get("status", {}).get("name", "")
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
        countsFresh=include_counts,
        releaseVersion=release_version,
    )

def system_divider_index(backlog: List[Any]) -> int | None:
    for index, item in enumerate(backlog):
        if isinstance(
            item,
            dict
        ) and str(item.get("kind", "")).strip() == SYSTEM_DIVIDER_KIND:
            return index
    return None

def ensure_system_sync_divider(backlog: List[Any]) -> None:
    primary_index = system_divider_index(backlog)
    if primary_index is None:
        backlog.insert(
            0,
            {
                "kind": SYSTEM_DIVIDER_KIND,
                "id": SYSTEM_DIVIDER_ID,
                "name": SYSTEM_DIVIDER_NAME,
                "color": SYSTEM_DIVIDER_COLOR,
            },
        )
        return

    primary_item = backlog[primary_index]
    if isinstance(primary_item, dict):
        primary_item["kind"] = SYSTEM_DIVIDER_KIND
        primary_item["id"] = SYSTEM_DIVIDER_ID
        primary_item["name"] = SYSTEM_DIVIDER_NAME
        if str(primary_item.get("color", "")).strip() == "":
            primary_item["color"] = SYSTEM_DIVIDER_COLOR

    duplicate_indexes: List[int] = []
    for index, item in enumerate(backlog):
        if index == primary_index:
            continue
        if isinstance(
            item,
            dict
        ) and str(item.get("kind", "")).strip() == SYSTEM_DIVIDER_KIND:
            duplicate_indexes.append(index)

    for index in reversed(duplicate_indexes):
        backlog.pop(index)

def collect_backlog_issue_keys_above_divider(backlog: List[Any]) -> set[str]:
    divider_idx = system_divider_index(backlog)
    if divider_idx is None:
        return set()

    issue_keys: set[str] = set()
    for index, item in enumerate(backlog):
        if index >= divider_idx:
            break
        if not isinstance(item, dict):
            continue
        if str(item.get(
            "kind",
            "feature"
        )).strip() in ("divider", SYSTEM_DIVIDER_KIND):
            continue
        issue_key = normalize_issue_key(item.get("issueKey") or item.get("id"))
        if issue_key is not None:
            issue_keys.add(issue_key)
    return issue_keys

def collect_track_issue_keys(tracks: Any) -> set[str]:
    if not isinstance(tracks, list):
        return set()

    issue_keys: set[str] = set()
    for track in tracks:
        if not isinstance(track, dict):
            continue
        feature = track.get("feature")
        if not isinstance(feature, dict):
            continue
        if str(feature.get(
            "kind",
            "feature"
        )).strip() in ("divider", SYSTEM_DIVIDER_KIND):
            continue
        issue_key = normalize_issue_key(feature.get("issueKey") or feature.get("id"))
        if issue_key is not None:
            issue_keys.add(issue_key)
    return issue_keys

def collect_virtual_features(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all virtual feature dicts from backlog and tracks."""
    virtual: List[Dict[str, Any]] = []
    for track in state.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        feature = track.get("feature")
        if isinstance(
            feature,
            dict
        ) and str(feature.get("kind", "")).strip() == VIRTUAL_FEATURE_KIND:
            virtual.append(feature)
    for item in state.get("backlog") or []:
        if isinstance(
            item,
            dict
        ) and str(item.get("kind", "")).strip() == VIRTUAL_FEATURE_KIND:
            virtual.append(item)
    return virtual

def sync_virtual_features(
    state: Dict[str, Any],
    headers: Dict[str, str],
    root_url: str,
) -> int:
    """Refresh units/completedUnits for every virtual feature in state.

    Returns the number of virtual features updated.
    """
    virtual_features = collect_virtual_features(state)
    updated = 0
    for feature in virtual_features:
        jql = str(feature.get("jql") or "").strip()
        if not jql:
            log.warning(
                "jira.virtual.skip id=%s reason=empty_jql",
                feature.get("id")
            )
            continue

        feature_id = feature.get("id", "?")
        started = time.monotonic()
        try:
            query = urlencode({
                "jql": jql,
                "fields": "status",
                "maxResults": 100,
            })
            url = f"{root_url}/rest/api/3/search/jql?{query}"
            issues = fetch_all_issues(url, headers)
            total = len(issues)
            completed = sum(
                1 for issue in issues
                if is_completed_status(
                    issue.get("fields", {}).get("status", {}).get("name", "")
                )
            )
            feature["units"] = total
            feature["completedUnits"] = completed
            updated += 1
            elapsed_ms = int((time.monotonic() - started) * 1000)
            log.info(
                "jira.virtual.done id=%s total=%s completed=%s elapsed_ms=%s",
                feature_id,
                total,
                completed,
                elapsed_ms,
            )
        except Exception as exc:
            log.error("jira.virtual.error id=%s error=%s", feature_id, exc)

    return updated
