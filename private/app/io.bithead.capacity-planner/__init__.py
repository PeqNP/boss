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
import os

from lib import get_config
from lib.model import User
from lib.server import authenticate_admin, get_users
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

def make_capacity(year: int, week: int, tasks: List[Task]):
    features = 0
    bugs = 0
    cs = 0
    planning = 0
    total = 0
    wontDo = 0

    devs = {}

    for task in tasks:
        _type, key, status, developer = task.type.lower(), task.key.lower(), task.status.lower(), task.developer
        if developer not in devs.keys():
            devs[developer] = 0

        if status in ["won't do", "duplicate"]:
            wontDo += 1
            continue
        else:
            devs[developer] += 1

         # Done, Needs Code Review, Needs QA, Done, etc.
        if key.startswith("so-"):
            cs += 1
            total += 1
        elif _type == "task":
            features += 1
            total += 1
        elif _type == "bug":
            bugs += 1
            total += 1
        elif _type in ["epic", "spike"]:
            planning += 1
            total += 1
        else:
            raise Exception(f"Unexpected status type ({task})")

    developers: List[Developer] = []
    for dev in devs:
        name = dev == "" and "Unassigned" or dev
        developers.append(Developer(name=name, capacity=0, finished=devs[dev]))

    report = TaskReport(
        features=features,
        bugs=bugs,
        cs=cs,
        planning=planning,
        total=total,
        wontDo=wontDo
    )

    capacity = Capacity(
        year=year,
        week=week,
        developers=developers,
        tasks=tasks,
        report=report
    )

    return capacity

def make_capacity_from_csv(year: int, week: int, file: Union[BufferedReader, "SpooledTemporaryFile"]):
    tasks: List[Task] = []

    with TextIOWrapper(file, encoding="utf-8") as fh:
        reader = csv.reader(fh)

        header = next(reader, None)
        if header != HEADERS:
            raise Exception(f"Headers must be in this format ({HEADERS})")

        for row in reader:
            _type, key, _, status, developer, _ = tuple(row)
            tasks.append(Task(
                type=_type.strip(),
                key=key.strip(),
                status=status.strip(),
                developer=developer.strip()
            ))

    return make_capacity(year, week, tasks)

async def _save_capacity(capacity: SaveCapacity):
    """ Save capacity to database. """
    db_key = f"{capacity.year}{capacity.week}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        await db.set(db_key, capacity.json())

async def _get_capacity(year: int, week: int) -> Capacity:
    """ Retrieve capacity from database. """
    db_key = f"{year}{week}"
    async with aiodbm.open(get_dbm_path(), "c") as db:
        value = await db.get(db_key)
    capacity = SaveCapacity.parse_raw(value)
    return make_capacity(capacity.year, capacity.week, capacity.tasks)

# MARK: API

router = APIRouter(prefix="/api/io.bithead.capacity-planner")

@router.post("/upload-csv", response_model=Capacity)
async def upload_csv(
    file: Annotated[UploadFile, File()],
    year: Annotated[int, Form()],
    week: Annotated[int, Form()],
    request: Request
):
    """ Upload a CSV, convert, and save Capacity. """
    user = await authenticate_admin(request)
    logging.debug(f"Parsing file ({file.filename})")
    file_content = file.read()
    capacity = make_capacity_from_csv(year, week, file.file)
    save_cap = SaveCapacity(year=capacity.year, week=capacity.week, tasks=capacity.tasks)
    await _save_capacity(save_cap)
    return capacity

@router.get("/capacity/{year}/{week}", response_model=Capacity)
async def get_capacity(year: int, week: int, request: Request):
    """ Get capacity week. """
    user = await authenticate_admin(request)
    return await _get_capacity(year, week)

@router.post("/capacity")
async def save_capacity(capacity: SaveCapacity, request: Request):
    """ Save capacity week. """
    user = await authenticate_admin(request)
    await _save_capacity(capacity)

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
