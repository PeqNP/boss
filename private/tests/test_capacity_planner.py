#!/usr/bin/env python3
#
# Capacity Planner
#

import logging
import pytest
import os
import sys

from lib.model import User
from libtest import *
from typing import List

logging.basicConfig(filename="capacity_planner.log", encoding="utf-8", level=logging.INFO)

def test_make_key():
    module = get_app_module("io.bithead.capacity-planner")
    key = module.make_key(2025, 9)
    assert key == "202509"
    key = module.make_key(2025, 11)
    assert key == "202511"

def test_week_label():
    module = get_app_module("io.bithead.capacity-planner")
    label = module.get_week_label(2025, 7)
    assert label == "Feb 16 thru Feb 22"

def test_import_csv():
    module = get_app_module("io.bithead.capacity-planner")
    path = os.path.join(os.path.dirname(__file__), "fixture", "capacity.csv")
    """ Not sure if this is needed yet.
    users: List[User] = [
        User(id=1, system=1, fullName="Donnie Wahlberg", email="donny@bithead.io", verified=True, enabled=True, avatarUrl=None),
        User(id=2, system=1, fullName="Joey McIntyre", email="joey@bithead.io", verified=True, enabled=True, avatarUrl=None),
        User(id=3, system=1, fullName="Jonathan Knight", email="jonathan@bithead.io", verified=True, enabled=True, avatarUrl=None),
        User(id=4, system=1, fullName="Danny Wood", email="danny@bithead.io", verified=True, enabled=True, avatarUrl=None),
    ]
    """
    with open(path, "rb") as fh:
        capacity = module.make_capacity_from_csv(2025, 8, fh)
    assert capacity is not None
    r = capacity.report
    assert r.features == 11
    assert r.bugs == 10
    assert r.cs == 1
    assert r.planning == 2
    assert r.total == 24
    assert r.wontDo == 5

    assert len(capacity.tasks) == 29
    assert len(capacity.developers) == 5 # 4 devs + Unassigned

    # NOTE: The order of the developers is determined when they are first seen
    # in the CSV.
    donnie = capacity.developers[0]
    joey = capacity.developers[1]
    jonathan = capacity.developers[2]
    unassigned = capacity.developers[3]
    danny = capacity.developers[4]
    #assert donnie.id == 1
    assert donnie.finished == 4
    #assert joey.id == 2
    assert joey.finished == 8
    #assert jonathan.id == 3
    assert jonathan.finished == 10
    #assert unassigned.id == 0
    # Remember: `Won't Do` tasks are not counted towards developer totals
    assert unassigned.name == "Unassigned"
    assert unassigned.finished == 1
    #assert danny.id == 4
    assert danny.finished == 1
