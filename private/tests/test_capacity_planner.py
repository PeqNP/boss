#!/usr/bin/env python3
#
# Capacity Planner
#

import logging
import importlib.util
import pytest
import os
import sys

from lib.model import User
from typing import List

logging.basicConfig(filename="capacity_planner.log", encoding="utf-8", level=logging.INFO)

def get_app_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "app")

def get_app_module(app):
    module_path = os.path.join(get_app_dir(), app, "__init__.py")
    if not os.path.isfile(module_path):
        raise Exception(f"App ({app}) module not found at path ({module_path}")
    spec_name = app.replace(".", "_").replace("-", "_")
    spec  = importlib.util.spec_from_file_location(spec_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_import_csv():
    module = get_app_module("io.bithead.capacity-planner")
    path = os.path.join(os.path.dirname(__file__), "fixture", "capacity.csv")
    users: List[User] = [
        User(id=1, system=1, fullName="Donnie Wahlberg", email="donny@bithead.io", verified=True, enabled=True, avatarUrl=None),
        User(id=2, system=1, fullName="Joey McIntyre", email="joey@bithead.io", verified=True, enabled=True, avatarUrl=None),
        User(id=3, system=1, fullName="Jonathan Knight", email="jonathan@bithead.io", verified=True, enabled=True, avatarUrl=None),
        User(id=4, system=1, fullName="Danny Wood", email="danny@bithead.io", verified=True, enabled=True, avatarUrl=None),
    ]
    with open(path, "rb") as fh:
        capacity = module.get_capacity_from_csv(2025, 8, fh, users)
    assert capacity is not None
    r = capacity.report
    assert r.features == 12
    assert r.bugs == 10
    assert r.cs == 1
    assert r.planning == 2
    assert r.total == 25
    assert r.wontDo == 4

    assert len(capacity.tasks) == 29
    assert len(capacity.developers) == 5 # 4 devs + Unassigned

    # NOTE: The order of the developers is determined when they are first seen
    # in the CSV.
    donnie = capacity.developers[0]
    joey = capacity.developers[1]
    jonathan = capacity.developers[2]
    unassigned = capacity.developers[3]
    danny = capacity.developers[4]
    assert donnie.id == 1
    assert donnie.finished == 7
    assert joey.id == 2
    assert joey.finished == 8
    assert jonathan.id == 3
    assert jonathan.finished == 10
    assert unassigned.id == 0
    assert unassigned.finished == 3
    assert danny.id == 4
    assert danny.finished == 1
