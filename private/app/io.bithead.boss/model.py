#
# Network models for the BOSS private service.
#
# Default and ServerInfo stay on the routes. These two are the workspace.
#

from pydantic import BaseModel
from typing import List


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
