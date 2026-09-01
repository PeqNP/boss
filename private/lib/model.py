from pydantic import BaseModel, Field
from typing import Callable, List, Optional


class AutomatedJob(BaseModel):
    """Work an app runs on a clock rather than on a request.

    An app declares these in its `jobs.py` and the service starts one task per
    job as it comes up. `run` is called on the event loop, the same place a
    request handler runs, because that is what every route in this service
    already does with its own synchronous database work.

    `seconds` is the gap between runs rather than a time of day. Nothing
    records when a job last ran, so a restart moves the next run rather than
    skipping it.
    """
    model_config = {"arbitrary_types_allowed": True}

    name: str
    run: Callable[[], int]
    seconds: int

class User(BaseModel):
    id: int
    system: int
    fullName: str
    email: str
    verified: bool
    enabled: bool
    avatarUrl: Optional[str] = None

class Friend(BaseModel):
    id: int
    userId: int
    name: str
    # NOTE: you must set the default to `None`. If the var doesn't exist
    # in the structure, this prevents pydantic from crashing.
    avatarUrl: Optional[str] = None

class Controller(BaseModel):
    bundleId: Optional[str]
    name: Optional[str]

def make_user(data: dict) -> User:
    return User(**data)

def make_friend(data: dict) -> Friend:
    return Friend(**data)
