#!/usr/bin/env python3
#
# BOSS OS & app services
#

import importlib.util
import logging
import os
import sys
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
        # Load modules from ./apps/<bundle_id>/__init__.py
        module_path = os.path.join(get_app_dir(), app, "__init__.py")
        if not os.path.isfile(module_path):
            logging.warning(f"App ({app}) does not have (__init__.py)")
            continue

        module_name = app
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None:
            logging.warning(f"Failed to create spec for module ({module_name})")
            continue

        module = importlib.util.module_from_spec(spec)
        # Register the module in sys.modules with the dotted name (e.g. io.bithead.boss)
        # This allows for relative imports
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logging.error(f"Failed to load module ({module_name}): {str(e)}")
            continue

        if hasattr(module, "start"):
            module.start()

        if hasattr(module, "router"): # Should have `router` var
            routers.append(module.router)
        else:
            logging.warning(f"Module ({module_name}) does not have a 'router' attribute")
            continue

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
