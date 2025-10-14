from pydantic import BaseModel
from typing import List, Optional

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

def make_user(data: dict) -> User:
    return User(**data)

def make_friend(data: dict) -> Friend:
    return Friend(**data)
