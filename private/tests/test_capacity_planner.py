#!/usr/bin/env python3
#
# Capacity Planner
#

import logging
import importlib.util
import pytest
import os
import sys

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
    with open(path, "rb") as fh:
        capacity = module.get_capacity_from_csv(2025, 8, fh)
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
    assert donnie.finished == 7
    assert joey.finished == 8
    assert jonathan.finished == 10
    assert unassigned.finished == 3
    assert danny.finished == 1
