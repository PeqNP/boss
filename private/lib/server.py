import httpx
import logging
import os

from lib import get_config
from lib.model import *
from fastapi import Depends, HTTPException, Request
from functools import wraps, update_wrapper
from inspect import Signature, signature, Parameter
from typing import Annotated, Any, Callable, Dict, List, Optional

REGISTER_ACL_ENDPOINT = "http://127.0.0.1:8081/acl/register"
USER_ENDPOINT = "http://127.0.0.1:8081/account/user"
USERS_ENDPOINT = "http://127.0.0.1:8081/account/users"
FRIENDS_ENDPOINT = "http://127.0.0.1:8081/friend"

# Models

class RegisterACL(BaseModel):
    acls: List[ACL]

class RegisteredACL(BaseModel):
    success: bool

# Functions

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

# ACL collected when services start. This is pushed to the BOSS server
# once all services have registered their ACL.
#
# e.g. {"Wordy": ["r", "x", "w"]}
REGISTERED_ACL: Dict[str, List[str]] = {}

def register_acl(acl_name: str, permission: str):
    global REGISTERED_ACL
    acl_name = acl_name.strip()
    permission = permission.strip()
    logging.debug(f"Registering ACL ({acl_name}) permission ({permission})")
    if REGISTERED_ACL.get(acl_name, None) is None:
        REGISTERED_ACL[acl_name] = []
    # I don't know if this is hard requirement yet. This should prevent
    # copy/paste issues. But it may be too strict too... however, my
    # understanding is that ACL is designed to have a unique signature
    # for every resource.
    if permission in REGISTERED_ACL[acl_name]:
        raise ValueError(f"Permission ({permission}) already exists for ACL ({acl_name})")
    REGISTERED_ACL[acl_name].append(permission)

async def register_acl_with_boss():
    """ Registers the ACL collected from services and sends to BOSS.

    This should be done after all services have started.
    """
    acls = []
    for name in REGISTERED_ACL:
        acls.append(ACL(name=name, permissions=REGISTERED_ACL[name]))
    payload = RegisterACL(acls=acls)

    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                REGISTER_ACL_ENDPOINT,
                json=payload.model_dump(),
                headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=str(e))

    body = response.json()
    registered = RegisteredACL.model_validate(body)
    if not registered.success:
        raise HTTPException(status_code=500, detail="Failed to register ACL")

def require_admin():
    """ Ensures user is an admin. """

    def decorator(func: Callable) -> Callable:
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
            request = kwargs.get("request", None)
            if request is None:
                raise ValueError("require_admin requires 'request: Request' parameter")

            user = await authenticate_admin(request)
            kwargs["boss_user"] = user

            return await func(*args, **kwargs)

        wrapper.__route__ = getattr(func, "__route__", None)
        return wrapper
    return decorator

def require_user(acl_name: Optional[str]=None, permission: Optional[str]=None):
    """ User ACL decorator.
    1. Registers ACL in DB at import time
    2. Injects `user: User` parameter at request time

    This MUST be called after the respective `@router.` call. e.g.
    ```
    @router.post("/solve", response_model=PossibleWords)
    @require_user("solve", "x")
    ```
    """

    if acl_name is None and permission is None:
        pass
    elif acl_name.strip() and permission.strip():
        pass
    else:
        raise ValueError("require_user expects acl_name and permission to both be present, or both be not present")

    def decorator(func: Callable) -> Callable:
        if acl_name is not None:
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
                raise ValueError("require_user requires 'request: Request' parameter")

            user = await authenticate_user(request, acl_name, permission)
            kwargs["boss_user"] = user

            return await func(*args, **kwargs)

        wrapper.__route__ = getattr(func, "__route__", None)
        wrapper.__acl_name__ = acl_name
        wrapper.__acl_permission__ = permission
        return wrapper
    return decorator
