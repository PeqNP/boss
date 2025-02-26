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

from datetime import datetime, timedelta
from lib import get_config
from lib.model import User
from lib.server import authenticate_admin, get_users
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from io import BufferedReader, TextIOWrapper
from pydantic import BaseModel
from starlette.status import HTTP_403_FORBIDDEN
from typing import Annotated, Any, List, Optional, Union

# CSV headers for JIRA import
HEADERS = ['Issue Type', 'Issue key', 'Status', 'Custom field (Developers)']

# Amount of time developer spends in each category, per day
TIME_LIESURE = 0.2
TIME_BUGS = 0.2
TIME_FEATURES = 0.6

# Amount of work distributed by work type
# Bugs include CS work. But it's not reported that way. They are currently
# separate categories.
EXP_BUGS = 0.2
# Features also includes Planning. But it's not reported that way. They are
# currently separate categories.
EXP_FEATURES = 0.8

# Computing min WU (Work Unit) / week
# One work unit is 2 days of work.
# e.g. 1 (2 days) + 1 (2 days) + 0.5 (1 day) = 2.5 WU / week
EXPECTED_WU_PER_DAY = 0.5 # Each day of week = 0.5 WU

DEFAULT_WORK_DAYS = 5

class RecordNotFound(Exception):
    pass

# MARK: Data Models

class Task(BaseModel):
    type: str
    key: str
    status: str
    developer: str

class TaskReport(BaseModel):
    features: int
    # Shows the percent of features complete compared to how much was estimated
    # for the week.
    featuresLabel: str
    bugs: int
    # Same as featuresLabel, but for bugs.
    bugsLabel: str
    cs: int # Customer Service
    planning: int
    total: int
    wontDo: int

class Developer(BaseModel):
    name: str
    capacity: int # Number of days available this week
    finished: int # Number of tickets (tasks/bugs/etc.) finished

class Capacity(BaseModel):
    # Provides the resource path necessary to access resource
    id: str
    # Displayable value that provides summary of capacity
    name: str
    dateRangeLabel: str
    year: int
    week: int
    developers: List[Developer]
    tasks: List[Task]
    report: Optional[TaskReport]
    # Number of days working this week
    workDays: int
    # Total estimated capacity (WUs) that will be complete this week
    totalCapacity: float

class SaveCapacity(BaseModel):
    year: int
    week: int
    developers: List[Developer]
    tasks: List[Task]
    workDays: int

# MARK: Package

def make_key(year, week):
    """ Creates a key from year and week.

    Zero-pads week so that sorting works.

    Args:
        year (int): The year (e.g. 2025)
        week (int): The ISO week number (1-53)

    Returns:
        str: Key used for dbm w/ week zero-padded
    """
    return f"{year}{week:02d}"

def get_dbm_path() -> str:
    """ Returns path to dbm (key/value store) path. """
    cfg = get_config()
    return os.path.join(cfg.db_path, "capacity-planner.dbm")

def get_week_label(year, week_number):
    """
    Get the week

    Args:
        year (int): The year (e.g., 2025).
        week_number (int): The ISO week number (1-53).

    Returns:
        tuple: (start_date, end_date) as datetime objects.
    """
    if not 1 <= week_number <= 53:
        raise ValueError("Week number must be between 1 and 53")

    # January 1st of the given year
    jan1 = datetime(year, 1, 1)

    # Find the first Sunday (week 1 starts on the first Sunday on or before Jan 1)
    jan1_weekday = jan1.weekday()  # 0 = Monday, 6 = Sunday
    days_to_sunday = (6 - jan1_weekday) % 7  # Days to next Sunday (or 0 if Jan 1 is Sunday)
    first_sunday = jan1 + timedelta(days=days_to_sunday)
    if first_sunday.year < year:  # If first Sunday is in previous year, move to next
        first_sunday += timedelta(days=7)

    # Calculate the Sunday of the desired week (week_number - 1 weeks after first Sunday)
    start_date = first_sunday + timedelta(weeks=week_number - 1)

    # End date is Saturday (6 days after Sunday)
    end_date = start_date + timedelta(days=6)

    # Validate the year (e.g., week 1 might be mostly in prev year)
    if start_date.year != year and end_date.year != year:
        raise ValueError(f"Week {week_number} does not exist in {year}")

    return f"{start_date.strftime('%b %d')} thru {end_date.strftime('%b %d')}"

def make_capacity(year: int, week: int, capacities: List[Developer], tasks: List[Task], workDays: int):
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

         # Everything else: Needs Code Review, Needs QA, Done, etc.
        if key.startswith("so-"):
            cs += 1
            total += 1
        elif _type in ["feature", "story", "task", "sub-task"]:
            features += 1
            total += 1
        elif _type == "bug":
            bugs += 1
            total += 1
        elif _type in ["epic", "spike"]:
            planning += 1
            total += 1
        else:
            raise HTTPException(status_code=400, detail=f"Unexpected status type ({_type}) in task ({task})")

    developers: List[Developer] = []
    total_capacity = 0
    for dev in devs:
        capacity = 0
        for cap in capacities:
            if cap.name == dev:
                capacity = cap.capacity
                break
        developers.append(Developer(
            name=dev,
            capacity=capacity,
            finished=devs[dev]
        ))
        # Capacity is the number of days available * the amount of work that
        # can be done per day. If WU = 0.5, and capacity is 5 days, this would
        # be 2.5 WU/week.
        total_capacity += (capacity * EXPECTED_WU_PER_DAY)
    # NOTE: Liesure time is not computed in capacity as developer
    # is not considered to be working during these periods.
    total_capacity = total_capacity * (TIME_BUGS + TIME_FEATURES)
    total_capacity = round(total_capacity, 2)

    actualFeatures = round((features / total) * 100)
    actualBugs = round((bugs / total) * 100)

    report = TaskReport(
        features=features,
        featuresLabel=f"Act. {actualFeatures}% ≈ {100 * EXP_FEATURES}%",
        bugs=bugs,
        bugsLabel=f"Act. {actualBugs}% ≈ {100 * EXP_BUGS}%",
        cs=cs,
        planning=planning,
        total=total,
        wontDo=wontDo
    )

    capacity = Capacity(
        id=f"{year}/{week}",
        name=f"{year}/{week} - Completed ({total}) / Capacity ({total_capacity})",
        dateRangeLabel=get_week_label(year, week),
        year=year,
        week=week,
        developers=developers,
        tasks=tasks,
        report=report,
        workDays=workDays,
        totalCapacity=total_capacity
    )

    return capacity

def make_capacity_from_csv(year: int, week: int, file: Union[BufferedReader, "SpooledTemporaryFile"]):
    tasks: List[Task] = []

    # utf-8-sig skips the BOM (Byte Order Mark) that is added to the first header
    # column in CSVs generated by JIRA.
    with TextIOWrapper(file, encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)

        header = next(reader, None)

        # Determine column numbers for the data used in the report
        columns = {}
        for name in HEADERS:
            try:
                col = header.index(name)
            except:
                logging.info(f"Headers ({header})")
                raise HTTPException(status_code=400, detail=f"Could not find header ({name}) in CSV")
            columns[name] = col

        for row in reader:
            # Extract only the values we want from the CSV.
            value = (
                row[columns[HEADERS[0]]],
                row[columns[HEADERS[1]]],
                row[columns[HEADERS[2]]],
                row[columns[HEADERS[3]]],
            )
            _type, key, status, developer = value
            dev = developer.strip()
            dev = len(dev) == 0 and "Unassigned" or dev
            tasks.append(Task(
                type=_type.strip(),
                key=key.strip(),
                status=status.strip(),
                developer=dev
            ))

    return make_capacity(year, week, [], tasks, DEFAULT_WORK_DAYS)

async def _save_capacity(capacity: SaveCapacity):
    """ Save capacity to database. """
    db_key = make_key(capacity.year, capacity.week)
    async with aiodbm.open(get_dbm_path(), "c") as db:
        await db.set(db_key, capacity.json())

async def _get_capacity(year: int, week: int) -> Capacity:
    """ Retrieve capacity from database. """
    db_key = make_key(year, week)
    async with aiodbm.open(get_dbm_path(), "c") as db:
        value = await db.get(db_key)
    if value is None:
        raise RecordNotFound(f"Capacity for year ({year}) and ({week}) not found")
    capacity = SaveCapacity.parse_raw(value.decode("utf-8"))
    return make_capacity(
        capacity.year,
        capacity.week,
        capacity.developers,
        capacity.tasks,
        capacity.workDays
    )

async def _get_all_capacities(limit: int=None) -> List[Capacity]:
    """ Returns all capacity records in descending order. """
    # TODO: Probably only need to get the last 20 records
    async with aiodbm.open(get_dbm_path(), "c") as db:
        # Get all keys asynchronously
        keys = await db.keys()
        logging.info(f"Found ({len(keys)}) in dbm")
        # Sort keys in descending order (decode if they're bytes)
        sorted_keys = sorted(keys, reverse=True)
        # Fetch all key-value pairs
        records: List[Capacity] = []
        for key in sorted_keys:
            value = await db.get(key)
            capacity = SaveCapacity.parse_raw(value.decode("utf-8"))
            records.append(make_capacity(
                capacity.year,
                capacity.week,
                capacity.developers,
                capacity.tasks,
                capacity.workDays
            ))
    logging.info(f"Records found ({len(records)})")
    return records

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
    save_cap = SaveCapacity(
        year=capacity.year,
        week=capacity.week,
        developers=capacity.developers,
        tasks=capacity.tasks,
        workDays=capacity.workDays
    )
    await _save_capacity(save_cap)
    return capacity

@router.get("/capacity", response_model=List[Capacity])
async def get_capacities(request: Request):
    """ Get all capacities ordered by year and date desc order. """
    user = await authenticate_admin(request)
    return await _get_all_capacities()

@router.get("/capacity/{year}/{week}", response_model=Capacity)
async def get_capacity(year: int, week: int, request: Request):
    """ Get capacity week. """
    user = await authenticate_admin(request)
    try:
        return await _get_capacity(year, week)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.post("/capacity", response_model=Capacity)
async def save_capacity(capacity: SaveCapacity, request: Request):
    """ Save capacity week. """
    user = await authenticate_admin(request)
    await _save_capacity(capacity)
    return make_capacity(
        capacity.year,
        capacity.week,
        capacity.developers,
        capacity.tasks,
        capacity.workDays
    )

@router.delete("/capacity/{year}/{week}")
async def delete_capacity(year: int, week: int, request: Request):
    """ Delete capacity week. """
    user = await authenticate_admin(request)
    db_key = make_key(year, week)
    async with aiodbm.open(get_dbm_path(), "c") as db:
        try:
            await db.delete(db_key)
        except KeyError:
            pass
