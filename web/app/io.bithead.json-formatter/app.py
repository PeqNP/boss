#
# JSON Formatter API
#

import asyncio
import logging
import json
import uvicorn

from lib import configure_logging
from fastapi import FastAPI, Request
from pydantic import BaseModel

description = """
# JSON Formatter

Simple JSON formatter.

---

[https://bithead.io](https://bithead.io).

© 2025 Bithead LLC. All rights reserved.
"""

app = FastAPI(
    title="JSON Formatter",
    description=description,
    version="1.0.0",
    contact={
        "name": "Bithead LLC",
        "url": "https://bithead.io",
        "email": "bitheadRL@protonmail.com"
    }
)

# MARK: Data Models

class Formatted(BaseModel):
    json: str

# MARK: Package

# MARK: API

@app.post("/app/io.bithead.json-formatter", response_model=Formatted)
async def format_json(body: Formatted, request: Request):
    """ Returns formatted JSON string. """
    # TODO: Pretty-fy JSON
    return Formatted(json=body.json)

if __name__ == "__main__":
    configure_logging(logging.INFO, service_name="io.bithead.json-formatter")
    uvicorn.run("app:app", host="0.0.0.0", port=8084, log_config=None, use_colors=False, ws=None)
