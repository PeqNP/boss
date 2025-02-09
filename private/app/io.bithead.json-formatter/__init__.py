#
# JSON Formatter API
#

import json

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

# MARK: Data Models

class Formatted(BaseModel):
    text: str
    decodeError: Optional[str]

class FormattedRequest(BaseModel):
    text: str

# MARK: Package

# MARK: API

router = APIRouter(prefix="/api/io.bithead.json-formatter")

@router.post("/", response_model=Formatted)
async def format_json(body: FormattedRequest, request: Request):
    """ Returns formatted JSON string. """
    text = body.text
    error = None
    try:
        text = json.loads(body.text)
        text = json.dumps(text, indent=4)
    except json.decoder.JSONDecodeError as exc:
        error = str(exc)
    return Formatted(text=text, decodeError=error)
