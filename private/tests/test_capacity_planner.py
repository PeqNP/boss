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
    capacity = module.get_capacity_from_csv("myfile.csv")
