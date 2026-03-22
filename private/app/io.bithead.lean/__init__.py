#
# Lean API
#

from fastapi import APIRouter, Request
from pydantic import BaseModel


class ServiceStatus(BaseModel):
    bundleId: str
    name: str
    status: str
    message: str


router = APIRouter(prefix="/api/io.bithead.lean")


@router.get("/", response_model=ServiceStatus)
async def get_status(request: Request):
    """Returns starter service metadata for the Lean app shell."""
    return ServiceStatus(
        bundleId="io.bithead.lean",
        name="Lean",
        status="Ready",
        message="Lean starter service is running."
    )