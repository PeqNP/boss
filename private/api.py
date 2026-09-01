#!/usr/bin/env python3
#
# BOSS OS & app services
#

import asyncio
import importlib.util
import logging
import os
import sys
import uvicorn

from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from lib import configure_logging
from lib.server import register_acl_with_boss
from typing import List

configure_logging(logging.INFO, service_name="boss")

def get_app_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "app")

def get_apps() -> List[str]:
    return os.listdir(get_app_dir())

def get_app_routers() -> List[APIRouter]:
    app_folders = get_apps()
    routers = []

    for app in app_folders:
        logging.info(f"Loading app ({app})")
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

def load_jobs(bundle):
    """An app's `jobs.py`, or `None` when it has no scheduled work.

    Loaded after the app itself, and registered under `<bundle>.jobs`, so the
    relative imports inside it resolve the way they do everywhere else.

    An app declaring one is expected to define `get_jobs`; without it the app
    is loaded and nothing is scheduled, which is reported rather than guessed
    at.
    """
    path = os.path.join(get_app_dir(), bundle, "jobs.py")
    if not os.path.isfile(path):
        return None
    name = f"{bundle}.jobs"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "get_jobs"):
        logging.warning(f"App ({bundle}) has jobs.py and no get_jobs()")
        return None
    return module


async def run_on_interval(bundle, job):
    """Run one job, forever, on its interval.

    Sleeps first, so starting the service does not run every job at once — a
    restart would otherwise sweep and remind on every deploy.

    Runs on the event loop, which is where a request handler runs: every route
    in this service does its own database work there, and a job is not special
    enough to be the one thing that does not.

    A job that raises is logged and tried again next interval. One bad hour is
    a job that did not run, not a service that stopped serving.
    """
    while True:
        await asyncio.sleep(job.seconds)
        try:
            job.run()
        except Exception as error:
            logging.error(f"Job ({bundle} {job.name}) failed: {error}")


def start_jobs(bundles):
    """Every app's scheduled work, as tasks that live as long as the service."""
    tasks = []
    for bundle in bundles:
        module = load_jobs(bundle)
        if module is None:
            continue
        for job in module.get_jobs():
            logging.info(f"Scheduling ({bundle} {job.name})"
                         f" every {job.seconds}s")
            tasks.append(asyncio.create_task(run_on_interval(bundle, job)))
    return tasks


@asynccontextmanager
async def register_services_with_boss(app):
    """ Called once when the app starts. """
    try:
        await register_acl_with_boss()
    except Exception as error:
        logging.error("Failed to register ACL with BOSS. Shutting down.")
        raise error

    tasks = start_jobs(get_apps())
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()

# Add routes to app.
#
# When Uvicorn is started, it _reloads_ this file! (Double importing via "api:app")
# Load these routes only once.
if __name__ != "__main__":
    description = """
    BOSS API

    Provides OS-level and BOSS app services.

    https://bithead.io

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
        },
        lifespan=register_services_with_boss
    )

    @app.get("/api/openapi.json", include_in_schema=False)
    async def openapi_json():
        return JSONResponse(app.openapi())

    @app.get("/api/docs", include_in_schema=False)
    def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )

    routers = get_app_routers()
    for router in routers:
        app.include_router(router)

    # UI test support: reset and snapshot each app's own database, which the
    # Swift `/debug/uitests` endpoints do not reach. Mounted only in
    # development, because these destroy data by design. See `debug.py`.
    import debug
    if debug.is_enabled():
        logging.info("Mounting UI test endpoints (/api/debug/uitests)")
        app.include_router(debug.router)

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8082,
        log_config=None,
        use_colors=False,
        ws=None
    )
