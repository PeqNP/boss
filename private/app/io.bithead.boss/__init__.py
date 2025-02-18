#
# BOSS API
#
# Provides facilities for BOSS such as Defaults, etc.
#

import asyncio
import aiodbm
import json

from lib.model import User
from lib.server import get_dbm_path, authenticate_user
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.status import HTTP_403_FORBIDDEN
from typing import Any, List, Optional

# MARK: Data Models

class Default(BaseModel):
    bundleId: str
    userId: int
    key: str
    value: Optional[Any]

class AppLink(BaseModel):
    bundleId: str
    name: str
    icon: str
    # TODO: If specific information about opening a file is required
    # there could be a `data` attribute here OR a path to a file to
    # DL, etc. It's not clear how files and folders will work at this
    # time.

class Workspace(BaseModel):
    desktop: List[AppLink]
    dock: List[AppLink]

# MARK: Package

def check_user(user_id, user):
    # UserID 1 is the super admin. This occurs when `login_enabled` is `False`.
    if user_id != user.id:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Can not access another user's resource"
        )

# MARK: API

router = APIRouter(prefix="/api/io.bithead.boss")

@router.get("/defaults/{bundle_id}/{user_id}/{key}", response_model=Default)
async def get_default(bundle_id: str, user_id: int, key: str, request: Request):
    """ Get user default value for key. """
    user = await authenticate_user(request)
    check_user(user_id, user)
    db_key = f"{bundle_id}/{user_id}/{key}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        value = await db.get(db_key)
    return Default(bundleId=bundle_id, userId=user_id, key=key, value=value)

@router.delete("/defaults/{bundle_id}/{user_id}/{key}")
async def delete_default(bundle_id: str, user_id: int, key: str, request: Request):
    """ Delete user default key. """
    user = await authenticate_user(request)
    check_user(user_id, user)
    db_key = f"{bundle_id}/{user_id}/{key}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        try:
            await db.delete(db_key)
        except KeyError:
            pass

@router.post("/defaults")
async def set_default(default: Default, request: Request):
    """ Set value for user default key. """
    user = await authenticate_user(request)
    check_user(default.userId, user)
    db_key = f"{default.bundleId}/{default.userId}/{default.key}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        await db.set(db_key, default.value)

@router.get("/workspace/{user_id}", response_model=Workspace)
async def get_default(user_id: int, request: Request):
    """ Returns user's workspace, which contains app links to open installed apps
    for both the dock and desktop (WIP). """
    user = await authenticate_user(request)
    check_user(user_id, user)

    db_key = f"desktop/{user_id}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        value = await db.get(db_key)
    if value:
        value = json.loads(value)
    else:
        # TODO: Read user preferences
        value = {
            "desktop": [
                AppLink(bundleId="io.bithead.boss-code", name="BOSSCode", icon="icon.svg"),
                AppLink(bundleId="io.bithead.test-manager", name="Test Manager", icon="icon.svg"),
                AppLink(bundleId="io.bithead.json-formatter", name="JSON Formatter", icon="icon.svg")
            ],
            "dock": [
                AppLink(bundleId="io.bithead.json-formatter", name="JSON Formatter", icon="icon.svg"),
                AppLink(bundleId="io.bithead.test-manager", name="Test Manager", icon="icon.svg"),
                AppLink(bundleId="io.bithead.boss-code", name="BOSSCode", icon="icon.svg")
            ]
        }

    return Workspace(
        desktop=value.get("desktop", []),
        dock=value.get("dock", [])
    )

@router.get("/workspace/desktop/{user_id}/{bundle_id}", response_model=Workspace)
async def set_desktop_link(user_id: int, bundle_id: str, request: Request):
    """ Add app link to desktop. """
    pass

@router.delete("/workspace/dock/{user_id}/{bundle_id}", response_model=Workspace)
async def delete_desktop_link(user_id: int, bundle_id: str, request: Request):
    """ Delete app link from desktop. """
    pass

@router.get("/workspace/dock/{user_id}/{bundle_id}", response_model=Workspace)
async def set_dock_link(user_id: int, bundle_id: str, request: Request):
    """ Add app link to dock. """
    pass

@router.delete("/workspace/dock/{user_id}/{bundle_id}", response_model=Workspace)
async def delete_dock_link(user_id: int, bundle_id: str, request: Request):
    """ Delete app link from dock. """
    pass
