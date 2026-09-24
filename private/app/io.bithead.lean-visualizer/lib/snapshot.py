"""Priority snapshots. A photograph of the tracked queue, and the diff from the one before it."""

import sqlite3
from datetime import date
from typing import Any, Dict, List

from ..model import FinishedFeature, MaterialLog, MaterialLogEntry, MaterialLogFeature
from ..db import *
from .board import (
    SYSTEM_DIVIDER_KIND,
    read_board_state,
)
from .schedule import build_schedule, feature_is_open
from .time import local_now

KIND_ORDER = ["entered", "sequence", "units", "blockage", "rate"]
TRACKED = ("track", "backlog")


def take_snapshot(conn: sqlite3.Connection, source: str) -> MaterialLog:
    """Photograph the tracked set and return the diff from the previous snapshot."""
    version = get_db_version(conn)
    version = migrate_to_1_0_0(conn, version)
    migrate_to_1_1_0(conn, version)
    state = read_board_state(conn)
    schedule = build_schedule(conn)
    now = local_now()
    created_on = now.date().isoformat()
    saved_at = now.isoformat(timespec="seconds")
    current = _photograph(state, schedule)
    previous_row = read_latest_priority_snapshot(conn)
    previous: Dict[str, sqlite3.Row] = {}
    previous_saved = ""
    if previous_row is not None:
        previous_saved = str(previous_row["saved_at"])
        for row in read_priority_snapshot_features(conn, int(previous_row["id"])):
            previous[str(row["feature_id"])] = row
    snapshot_id = insert_priority_snapshot(conn, saved_at, source)
    for row in current.values():
        insert_priority_snapshot_feature(conn, snapshot_id, row)
    raw_entries: List[Dict[str, Any]] = []
    finished: List[FinishedFeature] = []
    if previous_row is not None:
        raw_entries, finished = _diff(conn, current, previous, created_on, snapshot_id)
        for entry in raw_entries:
            if entry.get("update"):
                update_priority_blockage_entry(
                    conn,
                    entry["blockage_id"],
                    entry["ended_on"],
                    int(entry["days"]),
                    snapshot_id,
                )
            else:
                insert_priority_log_entry(conn, snapshot_id, entry)
        for item in finished:
            insert_priority_snapshot_finished(conn, snapshot_id, item.featureId, item.name, item.color)
    conn.commit()
    return _log(conn, snapshot_id, saved_at, previous_saved)


def latest_log(conn: sqlite3.Connection) -> MaterialLog:
    """The diff written by the newest snapshot. Empty before the first one."""
    version = get_db_version(conn)
    version = migrate_to_1_0_0(conn, version)
    migrate_to_1_1_0(conn, version)
    row = read_latest_priority_snapshot(conn)
    if row is None:
        return MaterialLog()
    previous = ""
    prior = conn.execute(
        "SELECT saved_at FROM priority_snapshots WHERE id < ? ORDER BY id DESC LIMIT 1",
        (int(row["id"]),),
    ).fetchone()
    if prior is not None:
        previous = str(prior["saved_at"])
    return _log(conn, int(row["id"]), str(row["saved_at"]), previous)


def _photograph(state: Dict[str, Any], schedule) -> Dict[str, Dict[str, Any]]:
    above, below = _split_backlog(state.get("backlog") or [])
    below_ids = {str(item.get("id") or "") for item in below}
    rows: Dict[str, Dict[str, Any]] = {}
    for track in schedule.tracks:
        tracked_bars = [
            bar for bar in track.bars
            if bar.featureId not in below_ids
        ]
        for position, bar in enumerate(tracked_bars):
            feature = _feature_by_id(state, bar.featureId) or {}
            ahead = tracked_bars[position - 1] if position else None
            rows[bar.featureId] = _row(
                feature or {"id": bar.featureId, "name": bar.name, "color": bar.color},
                "track",
                track.id,
                track.name,
                position,
                "" if ahead is None else ahead.featureId,
                "" if ahead is None else ahead.name,
                bar.finishOn,
                float(track.capacity),
            )
    backlog_only = [item for item in above if str(item.get("id") or "") not in rows]
    for position, feature in enumerate(backlog_only):
        feature_id = str(feature.get("id") or "")
        ahead = backlog_only[position - 1] if position else None
        rows[feature_id] = _row(
            feature,
            "backlog",
            "",
            "",
            position,
            "" if ahead is None else str(ahead.get("id") or ""),
            "" if ahead is None else str(ahead.get("name") or ""),
            "",
            0,
        )
    for position, feature in enumerate(below):
        feature_id = str(feature.get("id") or "")
        ahead = below[position - 1] if position else None
        rows[feature_id] = _row(
            feature,
            "below",
            "",
            "",
            position,
            "" if ahead is None else str(ahead.get("id") or ""),
            "" if ahead is None else str(ahead.get("name") or ""),
            "",
            0,
        )
    return rows


def _diff(
    conn: sqlite3.Connection,
    current: Dict[str, Dict[str, Any]],
    previous: Dict[str, sqlite3.Row],
    created_on: str,
    snapshot_id: int,
) -> tuple[List[Dict[str, Any]], List[FinishedFeature]]:
    entries: List[Dict[str, Any]] = []
    finished: List[FinishedFeature] = []
    for feature_id, row in current.items():
        if row["placement"] not in TRACKED:
            continue
        prior = previous.get(feature_id)
        if prior is None or str(prior["placement"]) not in TRACKED:
            entries.append(_entry(row, "entered", created_on, note="Entered the queue."))
            continue
        wrote_cause = False
        if str(prior["ahead_feature_id"] or "") != row["ahead_feature_id"]:
            name = row["ahead_name"]
            note = "Reprioritized to the front." if name == "" else f"Reprioritized behind {name}."
            entries.append(_entry(
                row,
                "sequence",
                created_on,
                note=note,
                ahead_feature_id=row["ahead_feature_id"],
                ahead_name=name,
            ))
            wrote_cause = True
        remaining = int(row["remaining_units"])
        prior_remaining = int(prior["remaining_units"] or 0)
        if remaining > prior_remaining:
            added = remaining - prior_remaining
            rate = float(row["weekly_rate"])
            days = int(round(added / rate * 7)) if rate > 0 else 0
            entries.append(_entry(
                row,
                "units",
                created_on,
                note=f"Added {added} units.",
                units_added=added,
                days=days,
                rate=rate,
            ))
            wrote_cause = True
        if _blockages(conn, row, created_on, snapshot_id, entries):
            wrote_cause = True
        finish = row["finish_on"]
        prior_finish = str(prior["finish_on"] or "")
        if not wrote_cause and finish != "" and prior_finish != "" and finish != prior_finish:
            entries.append(_entry(
                row,
                "rate",
                created_on,
                note=f"The lane's rate changed from {float(prior['weekly_rate']):g} to {float(row['weekly_rate']):g}.",
                days=(date.fromisoformat(finish) - date.fromisoformat(prior_finish)).days,
                previous_rate=float(prior["weekly_rate"] or 0),
                rate=float(row["weekly_rate"]),
            ))
    for feature_id, prior in previous.items():
        if str(prior["placement"]) not in TRACKED:
            continue
        row = current.get(feature_id)
        if row is not None and row["placement"] in TRACKED:
            continue
        if row is not None and row["placement"] == "below":
            continue
        finished.append(FinishedFeature(
            featureId=feature_id,
            name=str(prior["name"]),
            color=str(prior["color"]),
        ))
    return entries, finished


def _blockages(
    conn: sqlite3.Connection,
    row: Dict[str, Any],
    created_on: str,
    snapshot_id: int,
    entries: List[Dict[str, Any]],
) -> bool:
    wrote = False
    for span in row["blockages"]:
        blockage_id = str(span.get("id") or "")
        if blockage_id == "":
            continue
        began = str(span.get("beganOn") or "")
        ended = str(span.get("endedOn") or "")
        note = str(span.get("note") or "")
        existing = read_priority_blockage_entry(conn, blockage_id)
        if existing is None:
            entries.append(_entry(
                row,
                "blockage",
                created_on,
                note=note,
                blockage_id=blockage_id,
                began_on=began,
                ended_on=ended,
                days=_span_days(began, ended, created_on),
            ))
            wrote = True
            continue
        if str(existing["ended_on"] or "") == "" and ended != "":
            days = _span_days(str(existing["began_on"] or began), ended, created_on)
            entries.append(_entry(
                row,
                "blockage",
                created_on,
                note=str(existing["note"] or note),
                blockage_id=blockage_id,
                began_on=str(existing["began_on"] or began),
                ended_on=ended,
                days=days,
                update=True,
            ))
            wrote = True
    return wrote


def _span_days(began: str, ended: str, created_on: str) -> int:
    try:
        start = date.fromisoformat(began)
    except ValueError:
        return 0
    end_text = ended or created_on
    try:
        end = date.fromisoformat(end_text)
    except ValueError:
        return 0
    return (end - start).days


def _entry(row: Dict[str, Any], kind: str, created_on: str, **extra: Any) -> Dict[str, Any]:
    entry = {
        "feature_id": row["feature_id"],
        "name": row["name"],
        "color": row["color"],
        "kind": kind,
        "ahead_feature_id": "",
        "ahead_name": "",
        "units_added": 0,
        "blockage_id": "",
        "began_on": "",
        "ended_on": "",
        "note": "",
        "days": 0,
        "previous_rate": 0,
        "rate": float(row["weekly_rate"]),
        "created_on": created_on,
        "issue_key": row["issue_key"],
        "update": False,
    }
    entry.update(extra)
    return entry


def _log(conn: sqlite3.Connection, snapshot_id: int, saved_at: str, previous_saved: str) -> MaterialLog:
    stored = {
        str(row["feature_id"]): row
        for row in read_priority_snapshot_features(conn, snapshot_id)
    }
    grouped: Dict[str, List[MaterialLogEntry]] = {}
    meta: Dict[str, Dict[str, str]] = {}
    for row in read_priority_log_entries(conn, snapshot_id):
        feature_id = str(row["feature_id"])
        issue_key = ""
        if feature_id in stored:
            issue_key = str(stored[feature_id]["issue_key"] or "")
        meta[feature_id] = {
            "name": str(row["name"]),
            "color": str(row["color"]),
            "issueKey": issue_key,
        }
        grouped.setdefault(feature_id, []).append(MaterialLogEntry(
            kind=str(row["kind"]),
            featureId=feature_id,
            name=str(row["name"]),
            color=str(row["color"]),
            issueKey=issue_key,
            aheadFeatureId=str(row["ahead_feature_id"] or ""),
            aheadName=str(row["ahead_name"] or ""),
            unitsAdded=int(row["units_added"] or 0),
            blockageId=str(row["blockage_id"] or ""),
            createdOn=saved_at[:10],
            endedOn=str(row["ended_on"] or ""),
            note=str(row["note"] or ""),
            days=int(row["days"] or 0),
            previousRate=float(row["previous_rate"] or 0),
            rate=float(row["rate"] or 0),
        ))
    features = []
    for feature_id in sorted(grouped):
        entries = sorted(
            grouped[feature_id],
            key=lambda item: KIND_ORDER.index(item.kind) if item.kind in KIND_ORDER else 99,
        )
        features.append(MaterialLogFeature(
            featureId=feature_id,
            name=meta[feature_id]["name"],
            color=meta[feature_id]["color"],
            issueKey=meta[feature_id]["issueKey"],
            entries=entries,
        ))
    finished = [
        FinishedFeature(featureId=str(row["feature_id"]), name=str(row["name"]), color=str(row["color"]))
        for row in read_priority_snapshot_finished(conn, snapshot_id)
    ]
    return MaterialLog(
        savedAt=saved_at,
        previousSavedAt=previous_saved,
        features=features,
        finished=finished,
    )


def _split_backlog(backlog: Any) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    above: List[Dict[str, Any]] = []
    below: List[Dict[str, Any]] = []
    seen = False
    items = backlog if isinstance(backlog, list) else []
    if not any(isinstance(item, dict) and str(item.get("kind") or "") == SYSTEM_DIVIDER_KIND for item in items):
        seen = False
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "") == SYSTEM_DIVIDER_KIND:
            seen = True
            continue
        if not feature_is_open(item):
            continue
        if seen:
            below.append(item)
        else:
            above.append(item)
    return above, below


def _feature_by_id(state: Dict[str, Any], feature_id: str) -> Dict[str, Any] | None:
    for raw in state.get("tracks") or []:
        if isinstance(raw, dict) and isinstance(raw.get("feature"), dict):
            if str(raw["feature"].get("id") or "") == feature_id:
                return raw["feature"]
    for raw in state.get("backlog") or []:
        if isinstance(raw, dict) and str(raw.get("id") or "") == feature_id:
            return raw
    return None


def _row(
    feature: Dict[str, Any],
    placement: str,
    track_id: str,
    track_name: str,
    position: int,
    ahead_id: str,
    ahead_name: str,
    finish_on: str,
    weekly_rate: float,
) -> Dict[str, Any]:
    units = int(feature.get("units") or 0)
    completed = int(feature.get("completedUnits") or 0)
    return {
        "feature_id": str(feature.get("id") or ""),
        "issue_key": str(feature.get("issueKey") or ""),
        "name": str(feature.get("name") or ""),
        "color": str(feature.get("color") or ""),
        "placement": placement,
        "track_id": track_id,
        "track_name": track_name,
        "position": position,
        "ahead_feature_id": ahead_id,
        "ahead_name": ahead_name,
        "remaining_units": max(0, units - completed),
        "finish_on": finish_on or "",
        "weekly_rate": weekly_rate,
        "blockages": feature.get("blockages") if isinstance(feature.get("blockages"), list) else [],
    }
