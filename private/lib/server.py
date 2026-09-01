import httpx
import logging
import os
import sys

from lib import get_config
from lib.model import *
from fastapi import Depends, HTTPException, Request
from functools import wraps, update_wrapper
from inspect import Signature, signature, Parameter
from enum import Enum
from typing import Annotated, Any, Callable, Dict, List, Optional

BOSS_PRIVATE = "http://127.0.0.1:8081"

# Where private apps live, resolved from this file rather than imported from
# `api.py` — which imports this module.
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
REGISTER_ACL_ENDPOINT = f"{BOSS_PRIVATE}/private/acl/register"
USER_ENDPOINT = "http://127.0.0.1:8081/account/user"
USER_DETAILS_ENDPOINT = "http://127.0.0.1:8081/account/users/details"
FRIENDS_ENDPOINT = "http://127.0.0.1:8081/friend"
VERIFY_ENDPOINT = "http://127.0.0.1:8081/private/acl/verify"
SEND_NOTIFICATIONS_ENDPOINT = "http://127.0.0.1:8081/private/send/notifications"
SEND_EVENTS_ENDPOINT = "http://127.0.0.1:8081/private/send/events"

# Models

class ACLApp(BaseModel):
    bundleId: str
    features: List[str]
    # Role label to the features it holds, accumulated from what the app's
    # routes name. An app naming none receives a `default` role holding every
    # feature, which is what an app uses before it has roles of its own.
    roles: Dict[str, List[str]] = {}

class RegisterApps(BaseModel):
    apps: List[ACLApp]

class RegisteredACL(BaseModel):
    paths: Dict[str, int]

class VerifyACL(BaseModel):
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

async def _authenticate_admin(request: Request) -> User:
    user = await _authenticate_user(request)
    if user.id != 1:
        # 403, not a bare `Error`: that surfaces as a 500, and a client cannot
        # tell "you may not do this" from "the server is broken". One is a
        # screen the user should not have been offered; the other is a bug.
        raise HTTPException(status_code=403,
                            detail="Must be authenticated as an admin")
    # `require_admin` injects this as `boss_user`. Without the return it injects
    # `None`, and every admin route silently loses the identity of its caller.
    return user

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
            body = VerifyACL(bundleId=bundle_id, feature=feature)
            # A GET carrying a body, which is what `/private/acl/verify`
            # declares. `json=` is the httpx keyword; `body=` is not one, and
            # raised `TypeError` for as long as nothing called this.
            response = await client.request("GET", VERIFY_ENDPOINT,
                                            json=body.model_dump(),
                                            headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=str(e))

        # `/private/acl/verify` answers with the user fragment itself, where
        # `/account/user` wraps one in `{"user": ...}`.
        body = response.json()
        if not isinstance(body, dict) or "id" not in body:
            raise HTTPException(status_code=401, detail="Please sign in before accessing this resource")
        return make_user(body)

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

async def get_user_details(request: Request) -> List[User]:
    """ Returns all users in BOSS system, as whole records.

    `/account/users` answers a picker: an id and a name to show. That cannot
    fill a `User`, so anything that has to say *who* someone is reads this
    instead.
    """
    headers = get_headers(request)
    async with httpx.AsyncClient() as client:
        response = await client.get(USER_DETAILS_ENDPOINT, headers=headers)
        response.raise_for_status()
        body = response.json()
    return [make_user(user) for user in body.get("users", [])]

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
# The role BOSS supplies to an app that has declared none, holding every
# feature it has. An app names roles on every route that registers a feature,
# or names none anywhere — so this is never named by a route.
DEFAULT_ROLE = "default"

REGISTERED_APPS: Dict[str, ACLApp] = {}

def register_acl(app: str, feature: Optional[str],
                 roles: Optional[List[str]] = None):
    """ Register an app bundle ACL feature, and the roles that reach it.

    Both app and feature are expected to be stripped strings. `roles` are the
    labels an app's `Role` enum carries, which `require_acl` derives from the
    members it was given.

    An app's roles are whatever its routes name, gathered as the modules import
    and sent to BOSS with its features. There is nothing to keep in step: a
    role exists because a route named it.
    """
    global REGISTERED_APPS
    logging.info(f"Registering app ({app}) feature ({feature}) roles ({roles})")
    if REGISTERED_APPS.get(app, None) is None:
        REGISTERED_APPS[app] = ACLApp(bundleId=app, features=[], roles={})
    # NOTE: it's OK to have duplicate app and features. They get de-duped by
    # the server upon registration.
    if feature:
        REGISTERED_APPS[app].features.append(feature)
        for role in roles or []:
            REGISTERED_APPS[app].roles.setdefault(role, []).append(feature)


def calling_bundle(module: Optional[str] = None) -> Optional[str]:
    """The app a call came from, read off the calling module's name.

    `api.py` names each module after its directory, so a route lives in
    `io.bithead.scheduler` and a rule in `io.bithead.scheduler.lib`. The first
    three segments are the bundle either way.

    Reading it rather than taking it means an app has no argument to get wrong,
    and names only itself. Every private app shares one process, so this is a
    convenience rather than a boundary — deliberate misuse is a `bin/` check's
    business, not this function's.

    Pass a module name to resolve one directly; otherwise the caller's is used.
    """
    def bundle_of(name: str) -> Optional[str]:
        parts = (name or "").split(".")
        if len(parts) < 3:
            return None
        bundle = ".".join(parts[:3])
        # An app's directory is its bundle, so a name that is not one belongs
        # to something else under `private/`.
        return bundle if os.path.isdir(os.path.join(APP_DIR, bundle)) else None

    if module is not None:
        return bundle_of(module)

    # Outward until a frame belongs to an app. A fixed frame count would break
    # whenever a function is added between the caller and here.
    frame = sys._getframe(1)
    while frame is not None:
        found = bundle_of(frame.f_globals.get("__name__", ""))
        if found is not None:
            return found
        frame = frame.f_back
    return None


async def _post_to_boss(path: str, body: dict) -> None:
    """Send one private request to BOSS, raising what it answers."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BOSS_PRIVATE}{path}", json=body,
                                         headers={"Content-Type": "application/json"})
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code,
                                detail=e.response.text)
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=str(e))


def _bundle_of_caller() -> str:
    bundle = calling_bundle()
    if bundle is None:
        raise ValueError(
            "A license or role is granted by an app, and this call came from"
            " outside one."
        )
    return bundle


def _role_label(role: Enum) -> str:
    if not isinstance(role, Enum):
        raise TypeError(
            f"A role is a member of the app's `Role` enum, not"
            f" {type(role).__name__} ({role!r})."
        )
    label = str(role.value)
    if label.strip().lower() == DEFAULT_ROLE:
        raise ValueError(
            f"`{DEFAULT_ROLE}` is the role BOSS supplies to an app that has"
            f" declared none, and is granted to nobody."
        )
    return label


async def grant_license(user_id: int) -> None:
    """Give this app's license to a user.

    A license is what lets somebody open the app at all, checked before any
    ACL. Grant it when the app first has a reason to — a business created, an
    employee added.
    """
    await _post_to_boss("/private/acl/license",
                        {"bundleId": _bundle_of_caller(), "userId": user_id})


async def grant_role(user_id: int, role: Enum) -> None:
    """Give one of this app's roles to a user.

    Takes effect at their next sign-in, the roles being minted into the token.
    """
    await _post_to_boss("/private/acl/role",
                        {"bundleId": _bundle_of_caller(), "userId": user_id,
                         "role": _role_label(role), "revoke": False})


async def revoke_role(user_id: int, role: Enum) -> None:
    """Take one of this app's roles away from a user."""
    await _post_to_boss("/private/acl/role",
                        {"bundleId": _bundle_of_caller(), "userId": user_id,
                         "role": _role_label(role), "revoke": True})


async def register_acl_with_boss():
    """ Registers the ACL collected from services and sends to BOSS.

    This should be done after all services have started.

    Only the apps in this payload are reconciled. An app whose module failed to
    import registers nothing, is absent here, and is left as it was.

    An app is served by one backend. If a Swift service registers one of these
    bundles too, each registration rebuilds the other's roles from a payload
    that never named them, and nothing reports it.
    """
    global REGISTERED_APPS
    apps = REGISTERED_APPS.values()
    payload = RegisterApps(apps=apps)
    headers = {"Content-Type": "application/json"}
    logging.debug(f"Registering ACL ({payload}) REGISTERED_APPS ({REGISTERED_APPS})")

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

def require_acl(feature: Optional[str]=None, roles: Optional[List[Enum]]=None):
    """ Require a user to be signed in and have access to app and/or feature.
    1. Registers ACL in DB at import time
    2. Injects `boss_user: User` parameter at request time

    This MUST be called after the respective `@router.` call. e.g.
    ```
    @router.post("/solve", response_model=PossibleWords)
    @require_acl("solve.x", roles=[Role.OPERATOR])
    ```

    NOTE: `solve` represents the "feature". `x`, the permission.
    A feature is not required. Nor is a permission. It is possible
    to pass only `solve`.

    `roles` names who reaches this route, as members of the app's own `Role`
    enum:

    ```
    class Role(str, Enum):
        OPERATOR = "Operator"
        EMPLOYEE = "Employee"
    ```

    Members rather than strings, so a misspelling is an `AttributeError` when
    the module imports. The value is the label Settings shows.

    An app that declares no roles receives a `default` role holding every
    feature. Once it declares any, `bin/check-routes` reports a route that
    names a feature and no role.
    """
    # TODO: Get bundle ID of route
    if feature is not None:
        feature = feature.strip()
        if len(feature) < 1:
            feature = None

    labels: List[str] = []
    for role in roles or []:
        if not isinstance(role, Enum):
            raise TypeError(
                f"A role is a member of the app's `Role` enum, not"
                f" {type(role).__name__} ({role!r})."
            )
        label = str(role.value)
        if label.strip().lower() == DEFAULT_ROLE:
            raise ValueError(
                f"`{DEFAULT_ROLE}` is the role BOSS supplies to an app that has"
                f" declared none. An app either names roles on every route that"
                f" registers a feature, or names none anywhere."
            )
        labels.append(label)

    def decorator(func: Callable) -> Callable:
        bundle_id = func.__module__.strip()
        register_acl(bundle_id, feature, labels)

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

