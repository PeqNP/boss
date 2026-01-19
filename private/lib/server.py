import httpx
import logging
import os

from lib import get_config
from lib.model import *
from fastapi import Depends, HTTPException, Request
from functools import wraps, update_wrapper
from inspect import Signature, signature, Parameter
from typing import Annotated, Any, Callable, Dict, List, Optional

REGISTER_ACL_ENDPOINT = "http://127.0.0.1:8081/private/acl/register"
USER_ENDPOINT = "http://127.0.0.1:8081/account/user"
USERS_ENDPOINT = "http://127.0.0.1:8081/account/users"
FRIENDS_ENDPOINT = "http://127.0.0.1:8081/friend"
VERIFY_ENDPOINT = "http://127.0.0.1:8081/private/acl/verify"
SEND_NOTIFICATIONS_ENDPOINT = "http://127.0.0.1:8081/private/send/notifications"
SEND_EVENTS_ENDPOINT = "http://127.0.0.1:8081/private/send/events"

# Models

class ACLApp(BaseModel):
    bundleId: str
    features: List[str]

class ACLCatalog(BaseModel):
    name: str
    apps: List[ACLApp]

class RegisteredACL(BaseModel):
    catalog: Dict[str, int]

class VerifyACL(BaseModel):
    catalog: str
    bundleId: str
    feature: Optional[str]

class Notification(BaseModel):
    controller: Optional[Controller]
    deepLink: Optional[str]
    title: Optional[str]
    body: Optional[str]
    metadata: Optional[dict[str, str]]
    userId: int
    persist: bool

class SendNotifications(BaseModel):
    notifications: List[Notification]

class NotificationEvent(BaseModel):
    name: str
    userId: int
    data: dict[str, str]

class SendEvents(BaseModel):
    events: List[NotificationEvent]

# Functions

async def _authenticate_admin(request: Request):
    user = await _authenticate_user(request)
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

async def verify_user(request: Request, bundle_id: str, feature: Optional[str]) -> User:
    """ Get signed in user and compare ACL. """
    headers = get_headers(request)
    async with httpx.AsyncClient() as client:
        try:
            body = VerifyACL(catalog="python", bundleId=bundle_id, feature=feature)
            response = await client.post(VERIFY_ENDPOINT, body=body, headers=headers)
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

async def send_notifications(
    request: Request,
    user_ids: List[int],
    deep_link: Optional[str]=None,
    title: Optional[str]=None,
    body: Optional[str]=None,
    metadata: Optional[dict[str, str]]=None,
    persist: bool=False
):
    """ Send (the same) notification to users. """
    headers = get_headers(request)

    notifs = []
    for user_id in user_ids:
        notif = Notification(
            controller=None,
            deepLink=deep_link,
            title=title,
            body=body,
            metadata=metadata,
            userId=user_id,
            persist=False
        )
        notifs.append(notif)
    payload = SendNotifications(notifications=notifs)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SEND_NOTIFICATIONS_ENDPOINT,
            json=payload.model_dump(),
            headers=headers
        )
        response.raise_for_status()

async def send_events(request: Request, name: str, data: dict[str, str], user_ids: List[int]):
    """ Send (the same) notification to users. """
    headers = get_headers(request)
    events = []
    for user_id in user_ids:
        event = NotificationEvent(
            name=name,
            userId=user_id,
            data=data
        )
        events.append(event)
    payload = SendEvents(events=events)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SEND_EVENTS_ENDPOINT,
            json=payload.model_dump(),
            headers=headers
        )
        response.raise_for_status()

async def _authenticate_user(request: Request, bundle_id: str=None, feature: str=None) -> User:
    """ Authenticate the user with the Swift backend.

    The Swift backend will return the signed in user who has already been
    authenticated via BOSS.

    It is assumed that if login is disabled, this is a private server.
    Therefore, an admin user is returned when login is disabled.
    """
    try:
        if bundle_id:
            return await verify_user(request, bundle_id, feature)
        else:
            return await get_user(request)
    except HTTPException as exc:
        cfg = get_config()
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
# e.g. {"io.bithead.wordy": ACLApp(bundleId="io.bithead.wordy", features=["Wordy.r", "Wordy.x", "Wordy.w"])}
REGISTERED_APPS: Dict[str, ACLApp] = {}

def register_acl(app: str, feature: Optional[str]):
    """ Register an app bundle ACL feature.

    Both app and feature are expected to be stripped strings.
    """
    global REGISTERED_APPS
    logging.info(f"Registering app ({app}) feature ({feature})")
    if REGISTERED_APPS.get(app, None) is None:
        REGISTERED_APPS[app] = ACLApp(bundleId=app, features=[])
    # NOTE: it's OK to have duplicate app and features. They get de-duped by
    # the server upon registration.
    if feature:
        REGISTERED_APPS[app].features.append(feature)


async def register_acl_with_boss():
    """ Registers the ACL collected from services and sends to BOSS.

    This should be done after all services have started.
    """
    global REGISTERED_APPS
    apps = REGISTERED_APPS.values()
    payload = ACLCatalog(name="python", apps=apps)
    headers = {"Content-Type": "application/json"}
    logging.debug(f"Registering ACL catalog ({payload}) REGISTERED_APPS ({REGISTERED_APPS})")

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

    # TODO: The response could be used in the future
    #body = response.json()
    #registered = RegisteredACL.model_validate(body)

def require_admin():
    """ Require a user to be signed in as an admin.
    Injects `boss_user: User` parameter at request time

    This MUST be called after the respective `@router.` call. e.g.
    ```
    @router.post("/solve", response_model=PossibleWords)
    @require_admin()
    """

    def decorator(func: Callable) -> Callable:
        # If `boss_user` parameter exists, update its definition from `boss_user: User` to
        # Annotated[User, Depends(lambda: none)] to satisify FastAPI. Otherwise,
        # it thinks the `boss_user` parameter is going to be provided by the request.
        user_param_exists = False
        sig = signature(func)
        params = list(sig.parameters.values())
        for i, param in enumerate(params):
            if param.name == "boss_user" and param.annotation == User:
                params[i] = param.replace(
                    annotation=Annotated[User, Depends(lambda: None)]
                )
                user_param_exists = True
                break

        func.__signature__ = Signature(params)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            request = kwargs.get("request", None)
            if request is None:
                raise ValueError("require_admin requires 'request: Request' parameter")

            user = await _authenticate_admin(request)
            if user_param_exists:
                kwargs["boss_user"] = user

            return await func(*args, **kwargs)

        wrapper.__route__ = getattr(func, "__route__", None)
        return wrapper
    return decorator

def require_user():
    """ Require a user to be signed in to access endpoint.
    Injects `boss_user: User` parameter at request time

    This MUST be called after the respective `@router.` call. e.g.
    ```
    @router.post("/solve", response_model=PossibleWords)
    @require_user()
    ```

    NOTE: `solve` represents the "feature". `x`, the permission.
    A feature is not required. Nor is a permission. It is possible
    to pass only `solve`.
    """
    def decorator(func: Callable) -> Callable:
        user_param_exists = False
        sig = signature(func)
        params = list(sig.parameters.values())
        for i, param in enumerate(params):
            if param.name == "boss_user" and param.annotation == User:
                params[i] = param.replace(
                    annotation=Annotated[User, Depends(lambda: None)]
                )
                user_param_exists = True
                break
        func.__signature__ = Signature(params)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            request = kwargs.get("request", None)
            if request is None:
                raise ValueError("require_user requires 'request: Request' parameter")

            user = await _authenticate_user(request)
            if user_param_exists:
                kwargs["boss_user"] = user

            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_acl(feature: Optional[str]=None):
    """ Require a user to be signed in and have access to app and/or feature.
    1. Registers ACL in DB at import time
    2. Injects `boss_user: User` parameter at request time

    This MUST be called after the respective `@router.` call. e.g.
    ```
    @router.post("/solve", response_model=PossibleWords)
    @require_acl("solve.x")
    ```

    NOTE: `solve` represents the "feature". `x`, the permission.
    A feature is not required. Nor is a permission. It is possible
    to pass only `solve`.
    """
    # TODO: Get bundle ID of route
    if feature is not None:
        feature = feature.strip()
        if len(feature) < 1:
            feature = None

    def decorator(func: Callable) -> Callable:
        bundle_id = func.__module__.strip()
        register_acl(bundle_id, feature)

        user_param_exists = False
        sig = signature(func)
        params = list(sig.parameters.values())
        for i, param in enumerate(params):
            if param.name == "boss_user" and param.annotation == User:
                params[i] = param.replace(
                    annotation=Annotated[User, Depends(lambda: None)]
                )
                user_param_exists = True
                break
        func.__signature__ = Signature(params)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            request = kwargs.get("request", None)
            if request is None:
                raise ValueError("require_acl requires 'request: Request' parameter")

            user = await _authenticate_user(request, bundle_id, feature)
            if user_param_exists:
                kwargs["boss_user"] = user

            return await func(*args, **kwargs)
        return wrapper
    return decorator

