#
# BOSSCode API
#
# This service expects the user has already signed in with the Swift BOSS
# server. All authentication is done by making calls directly to the
# Swift backend.
#

import httpx
import logging
import json
import os
import uvicorn

from lib import configure_logging, get_config
from fastapi import FastAPI, HTTPException, Request
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, Self

LOCAL_SERVER = "http://127.0.0.1:8081/account/user"

description = """
### BOSSCode API

Provides all services for the BOSSCode application.

---

Access BOSS from [https://bithead.io](https://bithead.io).

© 2025 Bithead LLC
"""

app = FastAPI(
    title="BOSSCode",
    description=description,
    version="1.0.0",
    contact={
        "name": "Bithead LLC",
        "url": "https://bithead.io",
        "email": "bitheadRL@protonmail.com"
    }
)

# MARK: Data Models

class Project(BaseModel):
    id: str
    name: str

class Projects(BaseModel):
    projects: List[Project]

class ProjectSaved(BaseModel):
    success: bool

class Controller(BaseModel):
    name: str # Name of file
    singleton: bool

class ControllerConfig(BaseModel):
    isNew: bool
    name: str
    isSimple: bool
    endpoint: Optional[str]
    source: Optional[str]

class ControllerConfigRequest(BaseModel):
    isSimple: bool
    endpoint: Optional[str]
    source: Optional[str]

class File(BaseModel):
    name: str
    path: str
    isEditable: bool
    isImage: bool
    files: List[Self] = []

class FileSource(BaseModel):
    source: str

class ProjectStructure(BaseModel):
    bundleId: str
    name: str
    files: List[File] = []

class User(BaseModel):
    id: int
    system: int
    full_name: str
    email: str
    verified: bool
    enabled: bool
    avatar_url: Optional[str]

# MARK: Transformers

def make_user(data: dict) -> User:
    return User(
        id=data.get("id"),
        system=data.get("system"),
        full_name=data.get("fullName"),
        email=data.get("email"),
        verified=data.get("verified"),
        enabled=data.get("enabled"),
        avatar_url=data.get("avatarUrl")
    )

# MARK: Package

async def authenticate_user(request: Request) -> User:
    """ Authenticate the user with the Swift backend.

    The Swift backend gives us a user if authentication was successful, which
    can then be used for SQL queries.
    """
    cfg = get_config()
    if not cfg.login_enabled:
        return User(
            id=2,
            system=0,
            full_name="Guest",
            email="guest@bithead.io",
            verified=True,
            enabled=True,
            avatar_url=None
        )
    cookies = request.cookies
    headers = {"Cookie": "; ".join([f"{name}={value}" for name, value in cookies.items()])}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(LOCAL_SERVER, headers=headers)
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

def get_app_path() -> str:
    """ Returns path where BOSS apps are located. """
    cfg = get_config()
    return os.path.join(cfg.boss_path, "public", "boss", "app")

def get_bundle_path(bundle_id: str) -> str:
    """ Get path to project bundle path. """
    path = os.path.join(get_app_path(), bundle_id)
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path

def get_project_file_path(bundle_id: str, path: str) -> str:
    """ Returns the full (sandbox) path to a project file. """
    path = path.strip("/")
    full_path = os.path.join(get_bundle_path(bundle_id), path)
    return full_path

def get_controller_config_path(bundle_id: str, path: str) -> str:
    path = os.path.join(get_bundle_path(bundle_id), ".ide", path.strip("/"))
    p = Path(path)
    name = f"{p.name.split(".")[0]}.json"
    parent_path = p.parent
    if not os.path.isdir(parent_path):
        os.makedirs(parent_path, exist_ok=True)
    full_path = os.path.join(parent_path, name)
    return full_path

def is_image_file(file: str) -> bool:
    ext = Path(file).suffix.strip(".")
    is_image = ext in ["gif", "jpeg", "jpg", "png", "svg", "webp"]
    return is_image

def is_editable_file(file: str) -> bool:
    ext = Path(file).suffix.strip(".")
    is_editable = ext in ["html", "css", "js", "json"]
    return is_editable

def get_project_files(bundle_id: str) -> ProjectStructure:
    """ Returns all files in the bundle's directory.

    Only two levels of directories are supported.
    """
    path = os.path.join(get_bundle_path(bundle_id))
    _files = {}
    r = []
    for root, dirs, files in os.walk(path):
        for file in files:
            relative_path = os.path.join(root, file).replace(path, "").strip("/")
            f = File(
                name=file,
                path=relative_path,
                isEditable=is_editable_file(file),
                isImage=is_image_file(file)
            )
            if "/" in relative_path:
                d = relative_path.split("/")[0]
                if not _files.get(d, None):
                    folder = File(
                        name=d,
                        path=d,
                        isEditable=False,
                        isImage=False,
                        files=[f]
                    )
                    _files[d] = folder
                    r.append(folder)
                else:
                    _files[d].files.append(f)
            else:
                r.append(f)

    project = ProjectStructure(
        bundleId=bundle_id,
        name="Test Manager",
        files=r
    )
    return project

def get_file_contents(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File does not exist at path ({path})")
    with open(path, "r") as fh:
        contents = fh.read()
    return contents

def save_file_contents(path: str, contents: str):
    with open(path, "w") as fh:
        fh.write(contents)

# MARK: - API

@app.get("/boss-code", response_model=Projects)
async def get_projects(request: Request):
    """ Returns all projects on disk. """
    user = await authenticate_user(request)

    # TODO: Return only the projects that belong to the user. If login not enabled, show all.
    return Projects(
        projects=[
            Project(id="io.bithead.boss-code", name="BOSSCode"),
            Project(id="io.bithead.test-manager", name="Test Manager")
        ]
    )

@app.get("/boss-code/project/{bundle_id}", response_model=ProjectStructure)
async def get_project(bundle_id: str, request: Request):
    """ Loads a project. """
    user = await authenticate_user(request)
    return get_project_files(bundle_id)

@app.get("/boss-code/source/{bundle_id}/{path:path}", response_model=FileSource)
async def get_file_source(bundle_id: str, path: str, request: Request):
    """ Load project file source. """
    user = await authenticate_user(request)
    path = get_project_file_path(bundle_id, path)
    return FileSource(source=get_file_contents(path))

@app.post("/boss-code/source/{bundle_id}/{path:path}")
async def save_file_source(bundle_id: str, path: str, source: FileSource, request: Request):
    """ Save project file source. """
    user = await authenticate_user(request)
    path = get_project_file_path(bundle_id, path)
    save_file_contents(path, source.source)

@app.get("/boss-code/config/{bundle_id}/{path:path}", response_model=ControllerConfig)
async def get_controller_config(bundle_id: str, path: str, request: Request):
    """ Load controller preview config. """
    user = await authenticate_user(request)
    path = path.strip("/")
    if not path.startswith("controller/"):
        raise Error(f"Path ({path}) is not a controller")
    path = get_controller_config_path(bundle_id, path)
    name = Path(path).name.split(".")[0]
    try:
        contents = get_file_contents(path)
        obj = json.loads(contents)
        obj["isNew"] = False
    except FileNotFoundError:
        obj = {}
    return ControllerConfig(
        isNew=obj.get("isNew", True),
        name=name,
        isSimple=obj.get("isSimple", True),
        endpoint=obj.get("endpoint", None),
        source=obj.get("source", "")
    )

@app.post("/boss-code/config/{bundle_id}/{path:path}")
async def save_controller_config(bundle_id: str, path: str, config: ControllerConfigRequest, request: Request):
    """ Save controller preview config. """
    user = await authenticate_user(request)
    path = path.strip("/")
    if not path.startswith("controller/"):
        raise Error(f"Path ({path}) is not a controller")
    path = get_controller_config_path(bundle_id, path)
    save_file_contents(path, config.json())

if __name__ == "__main__":
    configure_logging(logging.INFO)
    uvicorn.run("app:app", host="0.0.0.0", port=8082, log_config=None, use_colors=False, ws=None)
