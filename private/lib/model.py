from pydantic import BaseModel
from typing import List, Optional, Self

class User(BaseModel):
    id: int
    system: int
    fullName: str
    email: str
    verified: bool
    enabled: bool
    avatarUrl: Optional[str]

def make_user(data: dict) -> User:
    return User(
        id=data.get("id"),
        system=data.get("system"),
        fullName=data.get("fullName"),
        email=data.get("email"),
        verified=data.get("verified"),
        enabled=data.get("enabled"),
        avatarUrl=data.get("avatarUrl")
    )

