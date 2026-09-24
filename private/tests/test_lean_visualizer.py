#!/usr/bin/env python3
#
# Lean Visualizer — the board, the rate, the schedule, and the report
#
# The rules under test are the ones a reader of the report can name. The calls
# are the ones the routes use.

import os
import sys

import asyncio
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from lib import get_config
from lib.model import User
from libtest import get_app_module

lv = get_app_module("io.bithead.lean-visualizer")


def fresh_database():
    lv.MODEL_DB_NAME = "test-lean-visualizer.sqlite3"
    path = os.path.join(get_config().db_path, lv.MODEL_DB_NAME)
    if os.path.exists(path):
        os.remove(path)


def iso(day):
    return day.isoformat()


def release(release_id, version, day):
    return {"id": release_id, "version": version, "date": iso(day)}


def save_board(releases):
    fresh_database()
    conn = lv.get_model_db_connection()
    lv.ensure_model_table(conn)
    state = lv.default_visualizer_state()
    state["releases"] = releases
    lv.upsert_model_row(conn, state, None)
    conn.close()


def open_board(state):
    fresh_database()
    conn = lv.get_model_db_connection()
    lv.ensure_model_table(conn)
    saved = lv.upsert_model_row(conn, state, None)
    return conn, saved


def week_sunday(day):
    """Sunday that opens the week containing `day`. Weeks are Sunday–Saturday."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def operator(name, track_id=""):
    return {"id": name.lower(), "name": name, "trackId": track_id}


def feature(feature_id, name, **extra):
    item = {
        "kind": "feature",
        "id": feature_id,
        "issueKey": "",
        "name": name,
        "units": 0,
        "completedUnits": 0,
        "manualEstWeeks": 0,
        "done": False,
        "color": "#336699",
        "pinnedTrackId": None,
        "jiraIssueType": "Epic",
    }
    item.update(extra)
    return item


def track(track_id, name, enabled=True, held=None):
    return {"id": track_id, "name": name, "enabled": enabled, "feature": held}


def rate_of(report, name):
    return next(item for item in report.rates.operators if item.operatorName == name)


def bar_names(schedule):
    return [bar.name for track in schedule.tracks for bar in track.bars]


# --- The exceptions ------------------------------------------------------
#
# A stored week is what the Jira weekly sync writes. These tests record the
# week directly so they do not call Jira, and so a week can sit in the past.


def test_checkpoint():
    today = date.today()
    save_board([
        release("rel_first", "1.0.0", today),
    ])
    conn = lv.get_model_db_connection()
    try:
        # describe: the release is the first
        saved = lv.save_checkpoint(conn, "rel_first")
        assert saved.windowStart == iso(today - timedelta(days=13)), "it: starts fourteen days before the date"
        assert saved.windowEnd == iso(today), "it: ends on the release date"
        assert lv.read_board_state(conn)["releases"][0]["version"] == "1.0.0", "it: leaves the board unchanged"

        # describe: the same release is saved again
        again = lv.save_checkpoint(conn, "rel_first")
        assert again.releaseId == "rel_first", "it: replaces that checkpoint"
    finally:
        conn.close()

    save_board([
        release("rel_prev", "1.0.0", today - timedelta(days=14)),
        release("rel_now", "1.1.0", today),
    ])
    conn = lv.get_model_db_connection()
    try:
        # describe: a release has a previous release
        saved = lv.save_checkpoint(conn, "rel_now")
        assert saved.windowStart == iso(today - timedelta(days=13)), "it: starts the day after the previous release"
    finally:
        conn.close()

    save_board([
        release("rel_future", "2.0.0", today + timedelta(days=1)),
    ])
    conn = lv.get_model_db_connection()
    try:
        # describe: the release date is tomorrow
        with pytest.raises(HTTPException) as refused:
            lv.save_checkpoint(conn, "rel_future")
        assert refused.value.status_code == 409, "it: refuses a release whose date has not arrived"

        # describe: the release is not on the board
        with pytest.raises(HTTPException) as missing:
            lv.save_checkpoint(conn, "rel_missing")
        assert missing.value.status_code == 409, "it: refuses a release that is not on the board"
    finally:
        conn.close()

    # describe: no checkpoint exists
    save_board([release("rel_open", "1.0.0", today)])
    conn = lv.get_model_db_connection()
    try:
        assert lv.build_report(conn).changes == [], "it: the change list is empty"
    finally:
        conn.close()


def test_forecast_change():
    today = date.today()
    sunday = week_sunday(today) - timedelta(days=7)

    def state_for(units):
        state = lv.default_visualizer_state()
        state["operators"] = [operator("Ada", "track_a")]
        state["tracks"] = [track("track_a", "Platform", held=feature(
            "feat", "Billing", units=units, color="#112233"
        ))]
        state["releases"] = [release("rel", "1.0.0", today)]
        return state

    conn, saved = open_board(state_for(0))
    try:
        lv.record_operator_week(conn, "Ada", sunday, 7, 0)
        lv.save_checkpoint(conn, "rel")

        # describe: the live finish is fourteen days after the checkpoint
        saved = lv.upsert_model_row(conn, state_for(14), saved.revision)
        changes = lv.build_report(conn).changes
        assert [item.featureId for item in changes] == ["feat"], "it: the feature is in the change list"
        assert changes[0].movedDays == 14, "it: counts a move of fourteen days"

        # describe: the live finish is thirteen days after the checkpoint
        lv.upsert_model_row(conn, state_for(13), saved.revision)
        assert lv.build_report(conn).changes == [], "it: a move of thirteen days is not a change"
    finally:
        conn.close()


def test_board():
    state = lv.default_visualizer_state()
    state["operators"] = [operator("Ada")]
    state["weeklyNotes"] = {"2026-09-13": "shipped"}
    state["releases"] = [release("rel", "1.0.0", date.today())]
    state["tracks"] = [track("track_a", "Platform", held=feature(
        "feat", "Billing", issueKey="FR-1", pillars=["Growth / Acquisition"],
        jiraIssueType="Epic"
    ))]
    fresh_database()
    conn = lv.get_model_db_connection()
    try:
        lv.ensure_model_table(conn)
        lv.store_pillars(conn, [{
            "issueKey": "FR-1",
            "pillars": ["Tech Debt / Stability"],
        }])
        saved = lv.upsert_model_row(conn, state, None)
        # describe: the board is saved with a matching revision
        assert saved.revision == 1, "it: the revision advances from an empty board"
        assert set(saved.state) == {
            "operators", "tracks", "backlog", "releases", "weeklyNotes"
        }, "it: the five keys round-trip"
        assert saved.state["weeklyNotes"]["2026-09-13"] == "shipped", "it: keeps the note"

        # describe: the payload carries a pillar on a feature
        held = saved.state["tracks"][0]["feature"]
        assert "pillars" not in held, "it: the saved state does not contain the pillar"
        assert lv.pillars_by_issue(conn)["FR-1"] == ["Tech Debt / Stability"], "it: feature_pillars is unchanged by the save"

        # describe: a feature has jiraIssueType
        again = lv.upsert_model_row(conn, saved.state, saved.revision)
        assert again.revision == 2, "it: a later save advances the revision"
        assert again.state["tracks"][0]["feature"]["jiraIssueType"] == "Epic", "it: a later save still has it"

        # describe: the revision is stale
        with pytest.raises(HTTPException) as stale:
            lv.upsert_model_row(conn, saved.state, saved.revision)
        assert stale.value.status_code == 409, "it: the save is refused"
        kept = lv.upsert_model_row(conn, saved.state, again.revision)
        assert kept.revision == 3, "it: the stored board is unchanged"
        assert kept.state["tracks"][0]["feature"]["name"] == "Billing", "it: the feature is the one that was saved"
    finally:
        conn.close()


def test_rate():
    today = date.today()
    current = week_sunday(today)
    complete = [current - timedelta(days=7 * (offset + 1)) for offset in range(8)]
    state = lv.default_visualizer_state()
    state["operators"] = [
        operator("Ada"),
        operator("Bea"),
        operator("Cal"),
        operator("Dee"),
    ]
    conn, _saved = open_board(state)
    try:
        for sunday in complete:
            lv.record_operator_week(conn, "Ada", sunday, 8, 0)
        lv.record_operator_week(conn, "Ada", current, 80, 0)
        for sunday in complete[:3]:
            lv.record_operator_week(conn, "Bea", sunday, 6, 0)
        lv.record_operator_week(conn, "Dee", complete[0], 4, 4)
        report = lv.build_report(conn)

        # describe: eight complete weeks are stored
        ada = rate_of(report, "Ada")
        assert ada.plannedPerWeek == 8, "it: the rate is their mean planned count"
        assert ada.plannedTotal == 64, "it: the total is the planned tasks in those weeks"
        assert ada.unplannedTotal == 0, "it: the unplanned total is beside it"
        assert ada.weeksCounted == 8, "it: counts each of the eight"

        # describe: the newest row is the current, unfinished week
        assert ada.plannedPerWeek == 8, "it: that row is outside the eight"

        # describe: three weeks are stored
        bea = rate_of(report, "Bea")
        assert bea.plannedPerWeek == 6, "it: the rate is the mean of those three"
        assert bea.weeksCounted == 3, "it: does not treat the missing weeks as zero"

        # describe: no week is stored
        cal = rate_of(report, "Cal")
        assert cal.plannedPerWeek == 0, "it: the rate is zero"
        assert cal.weeksCounted == 0, "it: counts no week"

        # describe: a week is zero planned and some unplanned
        dee = rate_of(report, "Dee")
        assert dee.plannedPerWeek == 0, "it: the zero counts in the mean"
        assert dee.unplannedPerWeek == 4, "it: the unplanned is reported beside it"
        assert dee.weeksCounted == 1, "it: the week still counts"
    finally:
        conn.close()


def test_schedule():
    today = date.today()
    sunday = week_sunday(today) - timedelta(days=7)
    state = lv.default_visualizer_state()
    state["operators"] = [operator("Ada", "track_a")]
    state["tracks"] = [track("track_a", "Platform", held=feature(
        "feat", "Billing", units=14, completedUnits=7, color="#112233",
        issueKey="FR-9"
    ))]
    conn, saved = open_board(state)
    try:
        lv.record_operator_week(conn, "Ada", sunday, 7, 0)
        schedule = lv.build_schedule(conn)
        bar = schedule.tracks[0].bars[0]

        # describe: a feature has remaining units and the track has a rate
        assert bar.finishOn == iso(today + timedelta(days=7)), "it: the duration is remaining divided by the rate"

        # describe: a feature has a color
        assert bar.color == "#112233", "it: the schedule bar uses that color"
        assert bar.issueKey == "FR-9", "it: the bar carries the issue key"

        # describe: manualEstWeeks is set and units are set
        held = feature(
            "feat", "Billing", units=14, completedUnits=7,
            manualEstWeeks=2, color="#112233"
        )
        revised = lv.upsert_model_row(conn, {
            **saved.state,
            "tracks": [track("track_a", "Platform", held=held)],
        }, saved.revision)
        manual = lv.build_schedule(conn).tracks[0].bars[0]
        assert manual.finishOn == iso(today + timedelta(days=14)), "it: the manual estimate is the duration"
    finally:
        conn.close()

    # describe: the track's rate is zero and there is no manual estimate
    state = lv.default_visualizer_state()
    state["operators"] = [operator("Ada", "track_a")]
    state["tracks"] = [track("track_a", "Platform", held=feature(
        "feat", "Billing", units=7
    ))]
    conn, _saved = open_board(state)
    try:
        bar = lv.build_schedule(conn).tracks[0].bars[0]
        assert bar.finishOn == "", "it: the finish date is empty"
    finally:
        conn.close()

    # describe: the backlog has the system divider
    state = lv.default_visualizer_state()
    state["operators"] = [operator("Ada", "track_b")]
    state["tracks"] = [
        track("track_a", "Paused", enabled=False),
        track("track_b", "Platform", enabled=True),
    ]
    state["backlog"] = [
        {
            "kind": "system-divider",
            "id": "system-sync-divider",
            "name": "Below this line",
            "color": "#ffe7c2",
        },
        feature("held", "Held", units=7, color="#abcdef"),
    ]
    conn, _saved = open_board(state)
    try:
        lv.record_operator_week(conn, "Ada", sunday, 7, 0)
        schedule = lv.build_schedule(conn)
        assert "Below this line" not in bar_names(schedule), "it: the divider has no bar"
        assert schedule.tracks[0].bars == [], "it: a disabled track is not where backlog work goes"
        assert schedule.tracks[1].bars[0].name == "Held", "it: a feature below it is scheduled"
        assert schedule.tracks[1].bars[0].color == "#abcdef", "it: the bar keeps the feature color"
    finally:
        conn.close()


def test_schedule_distribution():
    today = date.today()
    sunday = week_sunday(today) - timedelta(days=7)
    state = lv.default_visualizer_state()
    state["operators"] = [
        operator("Ada", "track_a"),
        operator("Bea", "track_b"),
        operator("Cal", "track_d"),
    ]
    state["tracks"] = [
        track("track_a", "Platform"),
        track("track_b", "Mobile"),
        track("track_d", "DevOps", held=feature(
            "soc", "SOC", pinnedTrackId="track_d"
        )),
    ]
    state["backlog"] = [
        feature("one", "One", units=7),
        feature("two", "Two", units=7),
        feature("three", "Three", units=7),
        feature("ops", "Pipeline", units=7, pinnedTrackId="track_d"),
    ]
    conn, _saved = open_board(state)
    try:
        lv.record_operator_week(conn, "Ada", sunday, 7, 0)
        lv.record_operator_week(conn, "Bea", sunday, 7, 0)
        lv.record_operator_week(conn, "Cal", sunday, 7, 0)
        names = {
            item.name: [bar.name for bar in item.bars]
            for item in lv.build_schedule(conn).tracks
        }
        # describe: unpinned backlog items are listed in priority order
        assert names["Platform"] == ["One", "Three"], "it: items are dealt across the enabled tracks in list order"
        assert names["Mobile"] == ["Two"], "it: the next item uses the next enabled track"
        # describe: a feature pins itself to DevOps
        assert names["DevOps"] == ["SOC", "Pipeline"], "it: that track receives only the features pinned to it"
    finally:
        conn.close()


def test_feature_sync_saves_pillars(monkeypatch):
    fresh_database()
    issues = [{
        "key": "FR-1",
        "fields": {
            "summary": "Grow",
            "issuetype": {"name": "Epic"},
            "fixVersions": [],
            "customfield_1": [
                {"value": "Growth / Acquisition"},
                {"value": "Tech Debt / Stability"},
            ],
        },
    }, {
        "key": "FR-2",
        "fields": {
            "summary": "Plain",
            "issuetype": {"name": "Epic"},
            "fixVersions": [],
        },
    }]

    def field_map(config, headers):
        return {"Strategic Pillar": "customfield_1"}

    jira = sys.modules[lv.get_jira_field_map.__module__]
    monkeypatch.setattr(jira, "get_jira_field_map", field_map)
    monkeypatch.setattr(lv, "fetch_all_issues", lambda url, headers: issues)

    async def verify(request, bundle_id, feature):
        return User(
            id=1, system=1, fullName="Ada", email="ada@example.com",
            verified=True, enabled=True,
        )

    monkeypatch.setattr("lib.server.verify_user", verify)

    # describe: a feature sync reads the Strategic Pillar field
    asyncio.run(lv.sync_jira(request=http_request()))
    conn = lv.get_model_db_connection()
    try:
        saved = lv.pillars_by_issue(conn)
    finally:
        conn.close()
    assert saved["FR-1"] == [
        "Growth / Acquisition",
        "Tech Debt / Stability",
    ], "it: both pillars on the issue are stored"
    assert saved["FR-2"] == [], "it: an issue with no pillar is stored as none"


def test_pillar():
    state = lv.default_visualizer_state()
    state["backlog"] = [
        feature(
            "grow", "Grow", issueKey="FR-1", units=10, completedUnits=4,
            pillars=["Growth / Acquisition", "New Features / Retention"]
        ),
        feature("plain", "Plain", issueKey="FR-2", units=3, completedUnits=0),
        feature("loose", "Loose", units=9),
        {
            "kind": "virtual-feature",
            "id": "virtual",
            "name": "Query",
            "issueKey": "FR-9",
            "units": 8,
            "jql": "project = FR",
        },
    ]
    conn, saved = open_board(state)
    try:
        lv.store_pillars(conn, [
            {"issueKey": "FR-1", "pillars": ["Growth / Acquisition", "New Features / Retention"]},
            {"issueKey": "FR-2", "pillars": []},
            {"issueKey": "FR-9", "pillars": []},
        ])
        report = lv.build_report(conn)
        rows = {item.pillar: item for item in report.pillars.open}

        # describe: a sync returns two pillars on one feature and none on another
        assert rows["Growth / Acquisition"].remainingUnits == 6, "it: the first counts in both groups"
        assert rows["Growth / Acquisition"].share == 50, "it: half of the open features are in that pillar"
        assert rows["New Features / Retention"].remainingUnits == 6, "it: the second pillar counts the same units"
        assert rows["Tech Debt / Stability"].share == 0, "it: a pillar with no features is zero percent"
        assert rows["Unassigned"].remainingUnits == 3, "it: the second is Unassigned"
        assert rows["Unassigned"].featureCount == 1, "it: a virtual feature is not in this section"
        assert rows["Tech Debt / Stability"].featureCount == 0, "it: a pillar with no work is still listed"
        assert rows["Process Efficiency / Cost Savings"].remainingUnits == 0, "it: every pillar has a row"

        # describe: a second sync does not mention an older issue key
        lv.store_pillars(conn, [{"issueKey": "FR-2", "pillars": ["Tech Debt / Stability"]}])
        kept = lv.pillars_by_issue(conn)
        assert kept["FR-1"] == ["Growth / Acquisition", "New Features / Retention"], "it: that key keeps its pillars"
        assert kept["FR-2"] == ["Tech Debt / Stability"], "it: the key this sync read is replaced"

        # describe: the board is saved
        lv.upsert_model_row(conn, saved.state, saved.revision)
        assert "FR-1" in lv.pillars_by_issue(conn), "it: pillars stay"
        assert "pillars" not in lv.read_board_state(conn)["backlog"][0], "it: the board JSON does not keep them"
    finally:
        conn.close()


def test_report():
    # describe: finished epics are handed to the grouping
    rows = {
        item.pillar: item.featureCount
        for item in lv.group_finished([
            {"pillars": ["Growth / Acquisition"]},
            {"pillars": ["Growth / Acquisition", "Tech Debt / Stability"]},
            {},
        ])
    }
    assert rows["Growth / Acquisition"] == 2, "it: they sum by pillar"
    assert rows["Tech Debt / Stability"] == 1, "it: a feature with two pillars counts in each"
    assert rows["Unassigned"] == 1, "it: a missing pillar is Unassigned"

    today = date.today()
    state = lv.default_visualizer_state()
    state["operators"] = [operator("Ada")]
    state["backlog"] = [feature(
        "debt", "Debt", issueKey="FR-3", units=5, completedUnits=1
    )]
    conn, _saved = open_board(state)
    try:
        lv.record_operator_week(conn, "Ada", date(2025, 12, 28), 3, 1)
        lv.store_pillars(conn, [{"issueKey": "FR-3", "pillars": ["Tech Debt / Stability"]}])
        report = lv.build_report(conn)

        # describe: weeks are stored from 28 December 2025
        week = next(item for item in report.rates.history if item.weekStart == "2025-12-28")
        assert week.operators[0].operatorName == "Ada", "it: history includes that week"
        assert week.operators[0].planned == 2, "it: the stored planned count is on that week"
        assert week.operators[0].unplanned == 1, "it: the stored unplanned count is on that week"
        assert week.weekStart == min(item.weekStart for item in report.rates.history), "it: that week is the start of history"

        # describe: open features have remaining units
        opened = {item.pillar: item for item in report.pillars.open}
        assert opened["Tech Debt / Stability"].remainingUnits == 4, "it: the open pillar rows sum those units"
        assert report.rates.windowStart > "2025-12-28", "it: the rate window stays the recent eight weeks"
    finally:
        conn.close()


def jira_stamp(day):
    offset = datetime.now().astimezone().strftime("%z")
    return day.isoformat() + "T12:00:00.000" + offset


def done_issue(key, day, developer, parent=None):
    fields = {
        "summary": key,
        "developers": [{"displayName": developer}],
    }
    if parent is not None:
        fields["parent"] = {"key": parent}
    return {
        "key": key,
        "fields": fields,
        "changelog": {
            "histories": [{
                "created": jira_stamp(day),
                "items": [{"field": "status", "toString": "Done"}],
            }],
        },
    }


def test_checkpoint_issues():
    today = date.today()
    state = lv.default_visualizer_state()
    state["operators"] = [operator("Ada")]
    state["releases"] = [release("rel", "1.0.0", today)]
    conn, _saved = open_board(state)
    try:
        # describe: an issue transitioned to done inside the window and names a Developer who is an operator
        saved = lv.save_checkpoint(conn, "rel", [
            done_issue("FR-10", today, "Ada", parent="FR-1"),
            done_issue("FR-11", today, "Ada"),
            done_issue("FR-12", today - timedelta(days=40), "Ada", parent="FR-1"),
            done_issue("FR-13", today, "Bob", parent="FR-1"),
        ])
        assert saved.issueCount == 2, "it: that operator is credited"
        rows = {item.issueKey: item for item in lv.read_checkpoint_issues(conn, "rel")}
        assert rows["FR-10"].planned is True, "it: planned when the issue has a parent"
        assert rows["FR-10"].operatorName == "Ada", "it: the credit names that operator"
        assert rows["FR-11"].planned is False, "it: an issue with no parent is unplanned"
        assert "FR-12" not in rows, "it: a transition outside the window is not credited"
        assert "FR-13" not in rows, "it: a developer who is not an operator is not credited"
    finally:
        conn.close()


def test_checkpoint_pull(monkeypatch):
    today = date.today()
    state = lv.default_visualizer_state()
    state["operators"] = [operator("Ada")]
    state["releases"] = [release("rel", "1.0.0", today)]
    conn, _saved = open_board(state)
    conn.close()
    seen = {}
    issue = done_issue("FR-20", today, "Ada", parent="FR-1")
    del issue["changelog"]

    def fake(names, start, end):
        seen["names"] = list(names)
        seen["start"] = start
        seen["end"] = end
        return [issue], "developers"

    config = get_config()
    previous_login = config.login_enabled
    config.login_enabled = True

    async def verify(request, bundle_id, feature):
        if feature != "checkpoint.w":
            raise HTTPException(status_code=403, detail="refused")
        return User(
            id=2,
            system=0,
            fullName="Pat",
            email="pat@example.com",
            verified=True,
            enabled=True,
        )

    monkeypatch.setattr("lib.server.verify_user", verify)
    monkeypatch.setattr(lv, "fetch_checkpoint_issues", fake)
    try:
        # describe: a checkpoint is saved from the board
        saved = asyncio.run(lv.put_checkpoint(release_id="rel", request=http_request()))
        assert seen["end"] == today.isoformat(), "it: the pull ends on the release date"
        assert seen["start"] == iso(today - timedelta(days=13)), "it: the first release uses the fourteen day window"
        assert seen["names"] == ["Ada"], "it: the pull names the board's operators"
        assert saved.issueCount == 1, "it: an issue the weekly query returns is credited"
        read = lv.get_model_db_connection()
        try:
            rows = lv.read_checkpoint_issues(read, "rel")
        finally:
            read.close()
        assert rows[0].issueKey == "FR-20", "it: the credited issue is the one Jira returned"
        assert rows[0].planned is True, "it: a parent still makes the credit planned"
    finally:
        config.login_enabled = previous_login


def http_request():
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    })


def status_of(handler, **kwargs):
    try:
        asyncio.run(handler(request=http_request(), **kwargs))
    except HTTPException as exc:
        return exc.status_code
    return 200


def test_access(monkeypatch):
    config = get_config()
    previous_login = config.login_enabled
    config.login_enabled = True
    grants = set()

    async def verify(request, bundle_id, feature):
        if feature not in grants:
            raise HTTPException(status_code=403, detail="refused")
        return User(
            id=2,
            system=0,
            fullName="Pat",
            email="pat@example.com",
            verified=True,
            enabled=True,
        )

    monkeypatch.setattr("lib.server.verify_user", verify)
    fresh_database()
    body = lv.SaveModelRequest(state=lv.default_visualizer_state())
    try:
        # describe: caller has no role
        assert status_of(lv.get_me) == 403, "it: GET /me is refused"
        assert status_of(lv.get_model) == 403, "it: GET /model is refused"

        grants.update(["schedule.r", "report.r"])
        # describe: caller is an Employee
        assert status_of(lv.put_model, body=body) == 403, "it: PUT /model is refused"
        assert status_of(lv.get_model) == 403, "it: GET /model is refused"
        assert status_of(lv.put_checkpoint, release_id="rel") == 403, "it: PUT /checkpoints/{releaseId} is refused"
        assert status_of(lv.get_schedule) == 200, "it: GET /schedule returns the forecast"
        assert status_of(lv.get_report) == 200, "it: GET /report returns the report"

        grants.update(["board.w", "board.r", "checkpoint.w"])
        # describe: caller is an Admin
        assert status_of(lv.put_model, body=body) == 200, "it: PUT /model is allowed"
    finally:
        config.login_enabled = previous_login
