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

router = APIRouter()

@router.post("/", response_model=Formatted)
async def format_json(body: Formatted, request: Request):
    """ Returns formatted JSON string. """
    # TODO: Pretty-fy JSON
    return Formatted(text=body.text)
