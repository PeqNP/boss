import httpx
import logging
import os

from lib import get_config
from lib.model import *
from fastapi import Depends, HTTPException, Request
from functools import wraps, update_wrapper
from inspect import Signature, signature, Parameter
from typing import Annotated, Any, Callable, Dict, List

USER_ENDPOINT = "http://127.0.0.1:8081/account/user"
USERS_ENDPOINT = "http://127.0.0.1:8081/account/users"
FRIENDS_ENDPOINT = "http://127.0.0.1:8081/friend"

async def authenticate_admin(request: Request):
    user = await authenticate_user(request)
    if user.id != 1:
        raise Error("Must be authenticated as an admin")

async def get_user_with_client(client, headers) -> User:
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

def get_headers(request: Request) -> Dict[str, str]:
    """ Get headers required for making calls to boss server. """
    cookies = request.cookies
    headers = {"Cookie": "; ".join([f"{name}={value}" for name, value in cookies.items()])}
    return headers

async def get_user(request: Request) -> User:
    """ Get signed in user. """
    headers = get_headers(request)
    async with httpx.AsyncClient() as client:
        return await get_user_with_client(client, headers)

async def get_friends(request: Request) -> (User, List[Friend]):
    """ Get user's friends.

    This also authenticates the user.
    """
    headers = get_headers(request)
    async with httpx.AsyncClient() as client:
        user = await get_user_with_client(client, headers)
        try:
            response = await client.get(FRIENDS_ENDPOINT, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=str(e))

        body = response.json()
    return (user, [make_friend(friend) for friend in body.get("friends", [])])

async def get_users(request: Request) -> List[User]:
    """ Returns all users in BOSS system. """
    users: List[User] = []
    headers = get_headers(request)
    async with httpx.AsyncClient() as client:
        response = await client.get(USERS_ENDPOINT, headers=headers)
        response.raise_for_status()
        users = response.json()
        for user in users:
            users.append(make_user(user))
    return users

async def authenticate_user(request: Request, acl_name: str=None, permission: str=None) -> User:
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

# --- ACL ---

ACL = []

def register_acl(acl_name: str, permission: str):
    logging.warning(f"Register name ({acl_name}) permission ({permission})")

# TODO: Decorator requires admin privileges
# TODO: Decorator requires user to be signed in

def user_acl(acl_name: str, permission: str):
    """ User ACL decorator.
    1. Registers ACL in DB at import time
    2. Injects `user: User` parameter at request time

    This MUST be called after the respective `@router.` call. e.g.
    ```
    @router.post("/solve", response_model=PossibleWords)
    @user_acl("solve", "x")
    ```
    """

    def decorator(func: Callable) -> Callable:
        register_acl(acl_name, permission)

        # If `boss_user` parameter exists, update its definition from `boss_user: User` to
        # Annotated[User, Depends(lambda: none)] to satisify FastAPI. Otherwise,
        # it thinks the `boss_user` parameter is going to be provided by the request.
        sig = signature(func)
        params = list(sig.parameters.values())
        for i, param in enumerate(params):
            if param.name == "boss_user" and param.annotation == User:
                params[i] = param.replace(
                    annotation=Annotated[User, Depends(lambda: None)]
                )
                updated = True
                break

        func.__signature__ = Signature(params)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            logging.info(f"Working!")
            request = kwargs.get("request", None)
            if request is None:
                raise ValueError("user_acl requires 'request: Request' parameter")

            # Authenticate
            user = await authenticate_user(request, acl_name, permission)

            # Make user available in router params
            kwargs["boss_user"] = user

            return await func(*args, **kwargs)

        # Store route info for later lookup
        wrapper.__route__ = getattr(func, "__route__", None)
        wrapper.__acl_name__ = acl_name
        wrapper.__acl_permission__ = permission
        return wrapper
    return decorator
