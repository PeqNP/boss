import httpx
import os

from lib import get_config
from lib.model import *
from fastapi import HTTPException, Request
from typing import List

USER_ENDPOINT = "http://127.0.0.1:8081/account/user"
USERS_ENDPOINT = "http://127.0.0.1:8081/account/users"

async def authenticate_admin(request: Request):
    user = await authenticate_user(request)
    if user.id != 1:
        raise Error("Must be authenticated as an admin")

async def get_user(request: Request) -> User:
    """ Get signed in user. """
    cookies = request.cookies
    headers = {"Cookie": "; ".join([f"{name}={value}" for name, value in cookies.items()])}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(USER_ENDPOINT, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=str(e))

        body = response.json()
        user = body.get("user", None)
        if user is None:
            raise HTTPException(status_code=401, detail="Please sign in before accessing this resource")
    return make_user(user)

async def get_users(request: Request) -> List[User]:
    """ Returns all users in BOSS system. """
    users: List[User] = []
    cookies = request.cookies
    headers = {"Cookie": "; ".join([f"{name}={value}" for name, value in cookies.items()])}
    async with httpx.AsyncClient() as client:
        response = await client.get(USERS_ENDPOINT, headers=headers)
        response.raise_for_status()
        users = response.json()
        for user in users:
            users.append(make_user(user))
    return users

async def authenticate_user(request: Request) -> User:
    """ Authenticate the user with the Swift backend.

    The Swift backend will return the signed in user who has already been
    authenticated via BOSS.

    It is assumed that if login is disabled, this is a private server.
    Therefore, an admin user is returned when login is disabled.
    """
    cfg = get_config()
    try:
        return await get_user(request)
    except HTTPException as exc:
        # If the server is not running and login is not required,
        # return Admin user.
        if exc.status_code != 401 and not cfg.login_enabled:
            return User(
                id=1,
                system=0,
                fullName="Admin",
                email="admin@bithead.io",
                verified=True,
                enabled=True,
                avatarUrl=None
            )
        raise exc

def get_boss_path() -> str:
    """ Get path to project bundle path. """
    cfg = get_config()
    return cfg.boss_path

def get_sandbox_path(bundle_id: str) -> str:
    """ Returns path to bundle's sandbox. """
    cfg = get_config()
    path = os.path.join(cfg.sandbox_path, bundle_id)
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path

def get_dbm_path() -> str:
    """ Returns path to dbm (key/value store) path. """
    cfg = get_config()
    return os.path.join(cfg.db_path, "boss.dbm")
