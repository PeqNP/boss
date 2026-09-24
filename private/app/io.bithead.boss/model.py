#
# Network models for the BOSS private service.
#
# Default and ServerInfo stay on the routes. The font catalog and the
# workspace are the shapes the client reads.
#

from pydantic import BaseModel
from typing import List


class SystemFont(BaseModel):
    """One face the font picker offers."""

    id: str
    name: str
    styles: List[str]


class SystemFonts(BaseModel):
    """The font picker's catalog."""

    fonts: List[SystemFont]


class AppLink(BaseModel):
    """One installed app on the desktop or in the dock."""

    bundleId: str
    name: str
    icon: str
    # Files and folders are not part of this plan. A link is an installed app.


class Workspace(BaseModel):
    """The desktop and the dock, each in order."""

    desktop: List[AppLink]
    dock: List[AppLink]
