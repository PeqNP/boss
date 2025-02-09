#
# JSON Formatter API
#

import json

from fastapi import APIRouter, Request
from pydantic import BaseModel

# MARK: Data Models

class Formatted(BaseModel):
    text: str

# MARK: Package

# MARK: API

router = APIRouter(prefix="/api/io.bithead.json-formatter")

@router.post("/", response_model=Formatted)
async def format_json(body: Formatted, request: Request):
    """ Returns formatted JSON string. """
    text = json.dumps(body.text, indent=4)
    return Formatted(text=body.text)
