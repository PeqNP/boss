#
# BOSS API
#
# Provides facilities for BOSS such as Defaults, etc.
#

import httpx
import logging
import json
import os
import uvicorn

from lib import configure_logging, get_config
from fastapi import FastAPI
from pathlib import Path
from pydantic import BaseModel
from server import authenticate_user
from typing import List, Optional, Self

description = """
### BOSS

Provides OS-level services such as `Defaults`.

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

# MARK: Data Models

class Default(BaseModel):
    key: str
    value: str

# MARK: Package

# MARK: API

@app.get("/os/defaults/{bundle_id}/{user_id}/{key}", response_model=Default)
async def get_projects(request: Request):
    """ Returns user's Defaults for app bundle. """
    user = await authenticate_user(request)
    # TODO

@app.post("/os/defaults/{bundle_id}/{user_id}/{key}")
async def save_file_source(bundle_id: str, path: str, source: FileSource, request: Request):
    """ Save user's Defaults for app bundle. """
    user = await authenticate_user(request)
    # TODO

if __name__ == "__main__":
    configure_logging(logging.INFO)
    uvicorn.run("app:app", host="0.0.0.0", port=8083, log_config=None, use_colors=False, ws=None)
