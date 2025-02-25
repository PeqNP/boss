#
# Capacity Planner API
#
# Provides tools to plan for capacity.
#

import asyncio
import aiodbm
import csv
import json
import logging

from lib.model import User
from lib.server import authenticate_admin
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from io import BufferedReader, TextIOWrapper
from pydantic import BaseModel
from starlette.status import HTTP_403_FORBIDDEN
from typing import Annotated, Any, List, Optional, Union

# CSV headers for JIRA import
HEADERS = ['Issue Type', 'Issue key', 'Issue id', 'Status', 'Custom field (Developers)', 'Custom field (Developers)Id']

# MARK: Data Models

class Task(BaseModel):
    type: str
    key: str
    status: str
    developer: str

class TaskReport(BaseModel):
    features: int
    bugs: int
    cs: int # Customer Service
    planning: int
    total: int
    wontDo: int

class Developer(BaseModel):
    id: int # BOSS user ID
    name: str
    capacity: int # Number of days available this week
    finished: int # Number of tickets (tasks/bugs/etc.) finished

class Capacity(BaseModel):
    year: int
    week: int
    developers: List[Developer]
    tasks: List[Task]
    report: Optional[TaskReport]

class SaveCapacity(BaseModel):
    year: int
    week: int
    developers: List[Developer]
    tasks: List[Task]

# MARK: Package

def get_dbm_path() -> str:
    """ Returns path to dbm (key/value store) path. """
    cfg = get_config()
    return os.path.join(cfg.db_path, "capacity-planner.dbm")

def get_report() -> TaskReport:
    report = TaskReport(
        features=14,
        bugs=12,
        cs=0,
        planning=0,
        total=26,
        wontDo=5
    )
    return report

def get_capacity_from_csv(year: int, week: int, file: Union[BufferedReader, "SpooledTemporaryFile"]):
    # TaskReport
    features = 0
    bugs = 0
    cs = 0
    planning = 0
    total = 0
    wontDo = 0

    devs = {}
    tasks: List[Task] = []

    with TextIOWrapper(file, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header != HEADERS:
            raise Exception(f"Headers must be in this format ({HEADERS})")
        for row in reader:
            task, key, _, status, developer, _ = tuple(row)
            if developer not in devs.keys():
                devs[developer] = 0
            if status != "won't do":
                devs[developer] += 1
            tasks.append(Task(
                type=task,
                key=key,
                status=status,
                developer=developer
            ))

            task = task.lower()
            status = status.lower()
            if status == "won't do":
                wontDo += 1
                continue
             # Done, Needs Code Review, Needs QA, Done, etc.
            if key.startswith("SO-"):
                cs += 1
                total += 1
            elif task == "task":
                features += 1
                total += 1
            elif task == "bug":
                bugs += 1
                total += 1
            elif task in ["epic", "spike"]:
                planning += 1
                total += 1
            else:
                raise Exception(f"Unexpected status type ({task})")

    developers: List[Developer] = []
    for dev in devs:
        # TODO: Map user to user in system
        name = dev == "" and "Unassigned" or dev
        developers.append(Developer(id=0, name=name, capacity=0, finished=devs[dev]))

    report = TaskReport(
        features=features,
        bugs=bugs,
        cs=cs,
        planning=planning,
        total=total,
        wontDo=wontDo
    )
    no_cap = Capacity(
        year=year,
        week=week,
        developers=developers,
        tasks=tasks,
        report=report
    )
    return no_cap

# MARK: API

router = APIRouter(prefix="/api/io.bithead.capacity-planner")

@router.get("/upload-csv", response_model=Capacity)
async def upload_csv(
    file: Annotated[UploadFile, File()],
    year: Annotated[int, Form()],
    week: Annotated[int, Form()],
    request: Request
):
    """ Get user default value for key. """
    user = await authenticate_admin(request)
    logging.debug(f"Parsing file ({file.filename})")
    file_content = file.read()
    no_cap = get_capacity_from_csv(year, week, file.file)
    # TODO: Save week year to database if it doesn't already exist(?)
    return no_cap

@router.get("/capacity/{year}/{week}", response_model=Capacity)
async def get_capacity(year: int, week: int, request: Request):
    """ Get capacity week. """
    user = await authenticate_admin(request)
    db_key = f"{year}{week}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        value = await db.get(db_key)
    no_cap = Capacity.parse_raw(value)
    # TODO: Compute TaskReport (Does this even work?)
    no_cap.report = get_report()
    return no_cap

@router.post("/capacity")
async def save_capacity(capacity: SaveCapacity, request: Request):
    """ Save capacity week. """
    user = await authenticate_admin(request)
    db_key = f"{year}{week}/{default.key}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        await db.set(db_key, capacity.json())

@router.delete("/capacity")
async def delete_capacity(year: int, week: int, request: Request):
    """ Delete capacity week. """
    user = await authenticate_admin(request)
    db_key = f"{year}{week}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        try:
            await db.delete(db_key)
        except KeyError:
            pass
