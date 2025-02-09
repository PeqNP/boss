from pydantic import BaseModel
from typing import List, Optional, Self

class User(BaseModel):
    id: int
    system: int
    full_name: str
    email: str
    verified: bool
    enabled: bool
    avatar_url: Optional[str]

def make_user(data: dict) -> User:
    return User(
        id=data.get("id"),
        system=data.get("system"),
        full_name=data.get("fullName"),
        email=data.get("email"),
        verified=data.get("verified"),
        enabled=data.get("enabled"),
        avatar_url=data.get("avatarUrl")
    )

