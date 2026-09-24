#
# Workspace rules.
#
# A signed-in user has a desktop and a dock. The guest is user id 2, and the
# user routes refuse that id. Names and icons come from installed.json.
#

import json
import os

from typing import List

from lib import get_config

from . import db
from .model import AppLink, Workspace

# A new account starts from this. It is not a seed.
USER_DESKTOP = (
    "io.bithead.json-formatter",
    "io.bithead.tutorial",
    "io.bithead.scheduler",
    "io.bithead.wordy",
)
USER_DOCK = (
    "io.bithead.scheduler",
)

# The same id the database seeds, and the client treats as the guest.
GUEST_USER_ID = 2


class ValidationError(Exception):
    """Input that cannot be accepted, with a message meant for whoever asked."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def guest_workspace() -> Workspace:
    """The guest desktop and dock."""
    return _as_workspace(db.links(GUEST_USER_ID))


def get_workspace(user_id: int) -> Workspace:
    """One signed-in user's workspace.

    The first read writes the starting list. User id 2 is refused.
    """
    _refuse_guest(user_id)
    rows = db.links(user_id)
    if not rows:
        db.replace_links(user_id, USER_DESKTOP, USER_DOCK)
        rows = db.links(user_id)
    return _as_workspace(rows)


def save_workspace(user_id: int, workspace: Workspace) -> Workspace:
    """Replace both lists. Names in the result are the catalog's."""
    _refuse_guest(user_id)
    catalog = _catalog()
    _check("desktop", workspace.desktop, catalog)
    _check("dock", workspace.dock, catalog)
    db.replace_links(
        user_id,
        [link.bundleId for link in workspace.desktop],
        [link.bundleId for link in workspace.dock]
    )
    return _as_workspace(db.links(user_id))


def remove_desktop(user_id: int, bundle_id: str) -> Workspace:
    """Remove one desktop icon. The dock is left as it was."""
    return _remove(user_id, "desktop", bundle_id)


def remove_dock(user_id: int, bundle_id: str) -> Workspace:
    """Remove one dock icon. The desktop is left as it was."""
    return _remove(user_id, "dock", bundle_id)


def _refuse_guest(user_id: int):
    if user_id == GUEST_USER_ID:
        raise ValidationError("The guest workspace is not edited here.")


def _remove(user_id: int, surface: str, bundle_id: str) -> Workspace:
    _refuse_guest(user_id)
    db.remove_link(user_id, surface, bundle_id)
    return _as_workspace(db.links(user_id))


def _check(surface: str, links: List[AppLink], catalog: dict):
    seen = set()
    for link in links:
        bundle_id = link.bundleId.strip()
        if bundle_id == "":
            raise ValidationError("An application is required.")
        if bundle_id in seen:
            raise ValidationError(
                f"That application is already on the {surface}."
            )
        seen.add(bundle_id)
        entry = catalog.get(bundle_id)
        if entry is None:
            raise ValidationError("That application is not installed.")
        if entry.get("system") is True:
            raise ValidationError(
                "A system application cannot be placed on the workspace."
            )
        icon = entry.get("icon")
        if icon is None or str(icon).strip() == "":
            raise ValidationError("That application has no icon.")


def _catalog() -> dict:
    path = os.path.join(
        get_config().boss_path,
        "public",
        "boss",
        "app",
        "installed.json"
    )
    with open(path) as handle:
        return json.load(handle)


def _as_workspace(rows: List[db.LinkRow]) -> Workspace:
    catalog = _catalog()
    desktop = []
    dock = []
    ordered = sorted(rows, key=lambda row: (row.surface, row.position))
    for row in ordered:
        entry = catalog.get(row.bundle_id) or {}
        icon = entry.get("icon") or ""
        link = AppLink(
            bundleId=row.bundle_id,
            name=entry.get("name") or row.bundle_id,
            icon=icon
        )
        if row.surface == "dock":
            dock.append(link)
        else:
            desktop.append(link)
    return Workspace(desktop=desktop, dock=dock)
