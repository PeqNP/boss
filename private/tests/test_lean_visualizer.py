#!/usr/bin/env python3
#
# Lean Visualizer — release list and checkpoint
#
# The rules under test are the ones a reader of the report can name: which
# releases the list keeps, and what saving a checkpoint records. The calls are
# the ones the routes use.

import os

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from lib import get_config
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


def test_release_options():
    today = date.today()
    state = lv.default_visualizer_state()
    state["releases"] = [
        release("past", "9.0.0", today - timedelta(days=21)),
        release("soon", "1.0.0", today + timedelta(days=21)),
        release("today", "3.0.0", today),
        release("next", "2.0.0", today + timedelta(days=7)),
        release("later", "4.0.0", today + timedelta(days=40)),
    ]

    # describe: one past release and four on or after today
    versions = [item.version for item in lv.build_release_options_from_state(state)]
    assert versions == ["3.0.0", "2.0.0", "1.0.0"], "it: keeps the next three, earliest date first"


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
