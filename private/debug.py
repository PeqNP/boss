#
# Debug endpoints for UI testing.
#
# The Swift layer already offers `/debug/uitests/...` to reset and snapshot the
# BOSS database. That covers users, sessions, and ACLs — but a Python private
# service keeps its own SQLite file, which those endpoints never touch. A UI
# test that creates data through an app's API therefore has no way to undo it,
# and every run leaves more behind.
#
# These are the counterpart, mounted under `/api` so nginx routes them here:
#
#   GET  /api/debug/uitests/reset                  empty every app's database
#   PUT  /api/debug/uitests/snapshot/{name}        save the current state
#   GET  /api/debug/uitests/snapshot/{name}        restore it
#
# PUT saves and GET restores, mirroring the Swift shape so both read the same.
#
# Restoring is a plain file copy here, where the Swift side has to restart its
# database: these services open a connection per statement and hold none open,
# so replacing the file underneath them is enough.
#
# **Mounted only when `env` is `dev`.** They destroy data by design.
#

import logging
import os
import shutil
import sys

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib import Environment, get_config

router = APIRouter(prefix="/api/debug/uitests")


class DebugResult(BaseModel):
    # The bundle ids acted on, so a caller can see what a bare request covered.
    apps: List[str]


def is_enabled() -> bool:
    return get_config().env == Environment.DEV


def _app_bundles() -> set:
    """Bundle ids on disk.

    `api.py` registers each app in `sys.modules` under its bundle id, but so is
    every module that app imports — and `lib.py`, `export.py` and the rest all
    hold a reference to `db`. Without this the same database would be reset
    once per submodule, and the response would name modules rather than apps.
    """
    app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
    if not os.path.isdir(app_dir):
        return set()
    return {name for name in os.listdir(app_dir)
            if os.path.isdir(os.path.join(app_dir, name))}


def _participating(bundle: Optional[str]) -> List[str]:
    """Apps with a database this can act on.

    An app takes part by having a `db` module with the three functions every
    private service already needs: where the file is, how to remove it, and how
    to create it. Nothing new to implement, and an app without a database is
    skipped rather than failing the request.
    """
    bundles = []
    for name in _app_bundles():
        if bundle is not None and name != bundle:
            continue
        module = sys.modules.get(name)
        if module is None:
            continue
        db = getattr(module, "db", None)
        if db is None or not hasattr(db, "get_db_path"):
            continue
        if not (hasattr(db, "delete_database") and hasattr(db, "start_database")):
            continue
        bundles.append(name)

    if bundle is not None and not bundles:
        raise HTTPException(status_code=404,
                            detail=f"No app named ({bundle}) with a database is loaded.")
    return sorted(bundles)


def _db(bundle: str):
    return getattr(sys.modules[bundle], "db")


def _snapshot_path(bundle: str, name: str) -> str:
    db = _db(bundle)
    directory = os.path.dirname(db.get_db_path())
    return os.path.join(directory, f"{name}.{bundle}.sqlite3")


def _safe(name: str) -> str:
    """A snapshot name is part of a filename, so it may not wander out of the
    directory it belongs in."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid snapshot name.")
    return name


@router.get("/reset", response_model=DebugResult)
async def reset(bundle: Optional[str] = None):
    """Empty every app's database, or one named app's.

    A test that starts from nothing does not have to name its fixtures
    uniquely, clean up after itself, or survive whatever an earlier run left
    behind — and cleanup is exactly what a failing test never reaches.
    """
    if not is_enabled():
        raise HTTPException(status_code=404, detail="Not found.")

    acted = _participating(bundle)
    for name in acted:
        db = _db(name)
        logging.info(f"Resetting database for ({name})")
        db.delete_database()
        db.start_database()
    return DebugResult(apps=acted)


@router.put("/snapshot/{name}", response_model=DebugResult)
async def save_snapshot(name: str, bundle: Optional[str] = None):
    """Save the current state under `name`."""
    if not is_enabled():
        raise HTTPException(status_code=404, detail="Not found.")

    name = _safe(name)
    acted = []
    for app in _participating(bundle):
        source = _db(app).get_db_path()
        if not os.path.isfile(source):
            continue
        logging.info(f"Saving snapshot ({name}) for ({app})")
        shutil.copyfile(source, _snapshot_path(app, name))
        acted.append(app)
    return DebugResult(apps=acted)


@router.get("/snapshot/{name}", response_model=DebugResult)
async def load_snapshot(name: str, bundle: Optional[str] = None):
    """Restore the state saved under `name`.

    The snapshot itself is left untouched, so one seeded state can be restored
    as many times as a suite needs — reach it once, then branch from it.
    """
    if not is_enabled():
        raise HTTPException(status_code=404, detail="Not found.")

    name = _safe(name)
    acted = []
    for app in _participating(bundle):
        snapshot = _snapshot_path(app, name)
        if not os.path.isfile(snapshot):
            # An app that had no data when the snapshot was taken has nothing
            # to restore, which is not an error for a multi-app request.
            continue
        logging.info(f"Restoring snapshot ({name}) for ({app})")
        shutil.copyfile(snapshot, _db(app).get_db_path())
        acted.append(app)

    if not acted:
        raise HTTPException(status_code=404, detail=f"No snapshot named ({name}).")
    return DebugResult(apps=acted)
