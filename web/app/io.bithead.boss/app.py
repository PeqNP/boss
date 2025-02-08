#
# BOSS API
#
# Provides facilities for BOSS such as Defaults, etc.
#

import asyncio
import aiodbm
import logging
import json
import os
import uvicorn

from lib import configure_logging
from lib.model import User
from lib.server import get_dbm_path, authenticate_user
from fastapi import FastAPI, HTTPException, Request
from pathlib import Path
from pydantic import BaseModel
from starlette.status import HTTP_403_FORBIDDEN
from typing import Any, List, Optional, Self

description = """
### BOSS

Provides OS-level services such as `Defaults`.

---

[https://bithead.io](https://bithead.io).

© 2025 Bithead LLC. All rights reserved.
"""

app = FastAPI(
    title="BOSS",
    description=description,
    version="1.0.0",
    contact={
        "name": "Bithead LLC",
        "url": "https://bithead.io",
        "email": "bitheadRL@protonmail.com"
    }
)

# MARK: Data Models

class Default(BaseModel):
    bundleId: str
    userId: int
    key: str
    value: Optional[Any]

class DeepLink(BaseModel):
    link: str
    name: str
    icon: str

class AppLink(BaseModel):
    bundleId: str
    name: str
    icon: str

class Workspace(BaseModel):
    # WIP: Desktop icons can be files or apps. This type will change in the
    # future. For now, this returns nothing. Ideally, it would be a deeplink
    # to the app and the resource to open.
    desktop: List[DeepLink]
    # Dock may eventually allow deep links
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

@app.get("/os/defaults/{bundle_id}/{user_id}/{key}", response_model=Default)
async def get_default(bundle_id: str, user_id: int, key: str, request: Request):
    """ Get user default value for key. """
    user = await authenticate_user(request)
    check_user(user_id, user)
    db_key = f"{bundle_id}/{user_id}/{key}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        value = await db.get(db_key)
    return Default(bundleId=bundle_id, userId=user_id, key=key, value=value)

@app.delete("/os/defaults/{bundle_id}/{user_id}/{key}")
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

@app.post("/os/defaults")
async def set_default(default: Default, request: Request):
    """ Set value for user default key. """
    user = await authenticate_user(request)
    check_user(default.userId, user)
    db_key = f"{default.bundleId}/{default.userId}/{default.key}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        await db.set(db_key, default.value)

@app.get("/os/workspace/{user_id}", response_model=Workspace)
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
        # TODO: This should return nothing by default
        value = {
            "desktop": [],
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

@app.get("/os/workspace/desktop/{user_id}/{bundle_id}", response_model=Workspace)
async def set_desktop_link(user_id: int, bundle_id: str, request: Request):
    """ Add app link to desktop. """
    pass

@app.delete("/os/workspace/dock/{user_id}/{bundle_id}", response_model=Workspace)
async def delete_desktop_link(user_id: int, bundle_id: str, request: Request):
    """ Delete app link from desktop. """
    pass

@app.get("/os/workspace/dock/{user_id}/{bundle_id}", response_model=Workspace)
async def set_dock_link(user_id: int, bundle_id: str, request: Request):
    """ Add app link to dock. """
    pass

@app.delete("/os/workspace/dock/{user_id}/{bundle_id}", response_model=Workspace)
async def delete_dock_link(user_id: int, bundle_id: str, request: Request):
    """ Delete app link from dock. """
    pass

if __name__ == "__main__":
    configure_logging(logging.INFO, service_name="io.bithead.boss")
    uvicorn.run("app:app", host="0.0.0.0", port=8083, log_config=None, use_colors=False, ws=None)
