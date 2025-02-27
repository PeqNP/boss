#!/usr/bin/env python3
#
# BOSS OS & app services
#

import logging
import os
import importlib.util
import uvicorn

from fastapi import FastAPI, APIRouter
from lib import configure_logging
from typing import List

configure_logging(logging.INFO, service_name="boss")

description = """
### BOSS

Provides OS-level and BOSS app services.

---

[https://bithead.io](https://bithead.io).

© 2025 Bithead LLC. All rights reserved.
"""

app = FastAPI(
    title="BOSS",
    description=description,
    version="1.0.0",
    contact={
        "name": "Bithead LLC",
        "url": "https://bithead.io",
        "email": "bitheadRL@protonmail.com"
    }
)

def get_app_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "app")

def get_apps() -> List[str]:
    return os.listdir(get_app_dir())

def get_app_routers() -> List[APIRouter]:
    app_folders = get_apps()

    routers = []
    for app in app_folders:
        # Load modules from ./app/<bundle_id>/__init__.py.
        module_path = os.path.join(get_app_dir(), app, "__init__.py")
        if not os.path.isfile(module_path):
            raise Exception(f"App ({app}) does not have a __init__.py")
            logging.warning("__init__.py does not exist")
        # Creates a name that can be used as a python module.
        # e.g. io.bithead.boss-code will be transformed to io_bithead_boss_code
        spec_name = app.replace("-", "_").replace(".", "_")
        spec = importlib.util.spec_from_file_location(spec_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Every loaded `module` will have a `router` var
        routers.append(module.router)
    return routers

# Add routes to app
# THIS MUST BE DONE BEFORE `__name__ == "__main__"`!
routers = get_app_routers()
for router in routers:
    app.include_router(router)

if __name__ == "__main__":
    for router in app.routes:
        logging.debug(f"Router ({router.name}) methods ({router.methods})")

    uvicorn.run("api:app", host="0.0.0.0", port=8082, log_config=None, use_colors=False, ws=None)
