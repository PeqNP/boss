#!/usr/bin/env python3
#
# BOSS private service — system catalog.
#

import pytest

from libtest import *

get_app_module("io.bithead.boss")
from io.bithead.boss import db, lib
from io.bithead.boss.fonts import get_system_fonts, system_font_ids
from io.bithead.boss.model import AppLink, Workspace

GUEST_DESKTOP = [
    "io.bithead.json-formatter",
    "io.bithead.tutorial",
    "io.bithead.lean-visualizer",
    "io.bithead.wordy",
]
GUEST_NAMES = [
    "JSON Formatter",
    "Tutorial",
    "Lean Visualizer",
    "Wordy",
]
USER_DESKTOP = [
    "io.bithead.json-formatter",
    "io.bithead.tutorial",
    "io.bithead.scheduler",
    "io.bithead.wordy",
]
USER_NAMES = [
    "JSON Formatter",
    "Tutorial",
    "Scheduler",
    "Wordy",
]


def test_system_fonts():
    """Chicago and Geneva, as the font picker lists them."""
    fonts = get_system_fonts()

    # describe: the catalog
    assert [f.id for f in fonts] == ["ChicagoFLF", "Geneva"], \
        "it: offers the two faces BOSS already draws with"
    assert [f.name for f in fonts] == ["Chicago", "Geneva"], \
        "it: names them as the picker shows them"
    assert system_font_ids() == ("ChicagoFLF", "Geneva")

    # describe: styles
    for face in fonts:
        assert face.styles == ["regular", "bold", "italic", "boldItalic"], \
            "it: offers Regular, Bold, Italic, and Bold Italic"


def fresh_database():
    db.set_database_name("test-workspace.sqlite3")
    db.delete_database()
    db.start_database()


def bundles(links):
    return [link.bundleId for link in links]


def link(bundle_id, name="Nope"):
    return AppLink(bundleId=bundle_id, name=name, icon="icon.svg")


def test_guest_workspace():
    """The guest desktop is the seeded list, and the dock is empty."""
    fresh_database()

    workspace = lib.guest_workspace()

    # describe: the guest list
    assert bundles(workspace.desktop) == GUEST_DESKTOP, \
        "it: returns JSON Formatter, Tutorial, Lean Visualizer, and Wordy"
    assert [item.name for item in workspace.desktop] == GUEST_NAMES, \
        "it: names them from the catalog"
    assert workspace.dock == [], \
        "it: returns an empty dock"

    # describe: who the rows belong to
    rows = db.links(2)
    assert [row.user_id for row in rows] == [2, 2, 2, 2], \
        "it: the rows are user id 2"
    again = lib.guest_workspace()
    assert again == workspace, \
        "it: a second read returns those same rows"
    assert len(rows) == len(db.links(2)), \
        "it: a second read does not insert them again"


def test_first_workspace():
    """A signed-in user with no rows starts from the account list."""
    fresh_database()

    # describe: the guest id
    before = lib.guest_workspace()
    with pytest.raises(lib.ValidationError):
        lib.get_workspace(2)
    assert lib.guest_workspace() == before, \
        "it: user id 2 is refused"

    workspace = lib.get_workspace(5)

    # describe: the starting list
    assert bundles(workspace.desktop) == USER_DESKTOP, \
        "it: returns JSON Formatter, Tutorial, Scheduler, and Wordy"
    assert [item.name for item in workspace.desktop] == USER_NAMES, \
        "it: names them from the catalog"
    assert bundles(workspace.dock) == ["io.bithead.scheduler"], \
        "it: returns Scheduler in the dock"
    stored = len(db.links(5))
    assert lib.get_workspace(5) == workspace, \
        "it: the second read returns that list"
    assert len(db.links(5)) == stored, \
        "it: the second read does not insert it again"


def test_two_users():
    """Each signed-in user has their own lists."""
    fresh_database()
    lib.get_workspace(5)
    lib.save_workspace(
        5,
        Workspace(
            desktop=[link("io.bithead.music", "Music")],
            dock=[]
        )
    )
    lib.save_workspace(
        6,
        Workspace(
            desktop=[link("io.bithead.wordy")],
            dock=[link("io.bithead.wordy")]
        )
    )

    # describe: two signed-in users
    assert bundles(lib.get_workspace(5).desktop) == ["io.bithead.music"], \
        "it: saving one user's desktop leaves the other's list as they saved it"
    assert bundles(lib.get_workspace(6).desktop) == ["io.bithead.wordy"]
    assert bundles(lib.guest_workspace().desktop) == GUEST_DESKTOP, \
        "it: leaves the guest rows as they were"


def test_save_workspace():
    """A save replaces both lists and answers with the catalog's names."""
    fresh_database()
    lib.get_workspace(5)
    current = lib.get_workspace(5)

    # describe: a full replacement
    saved = lib.save_workspace(
        5,
        Workspace(
            desktop=[
                link("io.bithead.wordy"),
                link("io.bithead.music", "Music"),
            ],
            dock=[link("io.bithead.tutorial", "Tutorial")]
        )
    )
    assert bundles(saved.desktop) == [
        "io.bithead.wordy",
        "io.bithead.music",
    ], "it: the desktop comes back in the order it was sent"
    assert bundles(saved.dock) == ["io.bithead.tutorial"], \
        "it: the dock comes back in the order it was sent"

    # describe: one surface changes
    kept = lib.save_workspace(
        5,
        Workspace(
            desktop=[link("io.bithead.music", "Music")],
            dock=current.dock
        )
    )
    assert bundles(kept.dock) == ["io.bithead.scheduler"], \
        "it: a desktop-only change, sent with the current dock, keeps the dock"

    # describe: an empty surface
    empty_dock = lib.save_workspace(
        5,
        Workspace(
            desktop=kept.desktop,
            dock=[]
        )
    )
    assert empty_dock.dock == [], \
        "it: an empty dock is saved and comes back empty"
    empty_desktop = lib.save_workspace(
        5,
        Workspace(
            desktop=[],
            dock=[link("io.bithead.scheduler", "Scheduler")]
        )
    )
    assert empty_desktop.desktop == [], \
        "it: an empty desktop is saved and comes back empty"

    # describe: one app on both
    both = lib.save_workspace(
        5,
        Workspace(
            desktop=[link("io.bithead.wordy")],
            dock=[link("io.bithead.wordy")]
        )
    )
    assert bundles(both.desktop) == ["io.bithead.wordy"], \
        "it: Wordy on the desktop and in the dock is saved as both"
    assert bundles(both.dock) == ["io.bithead.wordy"]
    assert both.desktop[0].name == "Wordy", \
        "it: a client name of Nope for Wordy comes back as Wordy"
    assert both.desktop[0].icon == "icon.svg", \
        "it: the icon comes back from the catalog"

    # describe: the guest id
    before = lib.guest_workspace()
    with pytest.raises(lib.ValidationError):
        lib.save_workspace(2, both)
    assert lib.guest_workspace() == before, \
        "it: user id 2 is refused, and the guest rows stay"


def test_remove_desktop():
    """Delete takes one app off the desktop and leaves the dock."""
    fresh_database()
    lib.get_workspace(5)

    # describe: Delete on a desktop icon
    removed = lib.remove_desktop(5, "io.bithead.tutorial")
    assert bundles(removed.desktop) == [
        "io.bithead.json-formatter",
        "io.bithead.scheduler",
        "io.bithead.wordy",
    ], "it: the remaining desktop icons keep their order"
    assert bundles(removed.dock) == ["io.bithead.scheduler"], \
        "it: leaves the dock"

    # describe: an app that is not on the desktop
    untouched = lib.remove_desktop(5, "io.bithead.music")
    assert untouched == removed, \
        "it: a bundle that is not on the desktop leaves the workspace as it was"

    # describe: an app that is also in the dock
    still = lib.remove_desktop(5, "io.bithead.scheduler")
    assert "io.bithead.scheduler" not in bundles(still.desktop)
    assert bundles(still.dock) == ["io.bithead.scheduler"], \
        "it: removing Scheduler from the desktop leaves Scheduler in the dock"

    # describe: the guest id
    before = lib.guest_workspace()
    with pytest.raises(lib.ValidationError):
        lib.remove_desktop(2, "io.bithead.wordy")
    assert lib.guest_workspace() == before, \
        "it: user id 2 is refused, and the guest desktop stays"


def test_remove_dock():
    """Delete takes one app off the dock and leaves the desktop."""
    fresh_database()
    lib.save_workspace(
        5,
        Workspace(
            desktop=[
                link("io.bithead.scheduler", "Scheduler"),
                link("io.bithead.wordy"),
            ],
            dock=[
                link("io.bithead.scheduler", "Scheduler"),
                link("io.bithead.wordy"),
                link("io.bithead.music", "Music"),
            ]
        )
    )

    # describe: Delete on a dock icon
    removed = lib.remove_dock(5, "io.bithead.wordy")
    assert bundles(removed.dock) == [
        "io.bithead.scheduler",
        "io.bithead.music",
    ], "it: the remaining dock icons keep their order"
    assert bundles(removed.desktop) == [
        "io.bithead.scheduler",
        "io.bithead.wordy",
    ], "it: leaves the desktop"

    # describe: an app that is not on the dock
    untouched = lib.remove_dock(5, "io.bithead.tutorial")
    assert untouched == removed, \
        "it: a bundle that is not on the dock leaves the workspace as it was"

    # describe: an app that is also on the desktop
    still = lib.remove_dock(5, "io.bithead.scheduler")
    assert bundles(still.dock) == ["io.bithead.music"]
    assert "io.bithead.scheduler" in bundles(still.desktop), \
        "it: removing Scheduler from the dock leaves Scheduler on the desktop"

    # describe: the last icon
    empty = lib.remove_dock(5, "io.bithead.music")
    assert empty.dock == [], \
        "it: deleting the last dock icon returns an empty dock"

    # describe: the guest id
    before = lib.guest_workspace()
    with pytest.raises(lib.ValidationError):
        lib.remove_dock(2, "io.bithead.wordy")
    assert lib.guest_workspace() == before, \
        "it: user id 2 is refused, and the guest rows stay"


def test_save_rejects():
    """A list the catalog will not hold is refused, and nothing is written."""
    fresh_database()
    current = lib.get_workspace(5)

    def unchanged(workspace, message):
        with pytest.raises(lib.ValidationError) as caught:
            lib.save_workspace(5, workspace)
        assert str(caught.value) == message
        assert lib.get_workspace(5) == current, \
            "it: the stored list is unchanged"

    # describe: a list the catalog will not hold
    unchanged(
        Workspace(
            desktop=[link("io.bithead.not-an-app")],
            dock=current.dock
        ),
        "That application is not installed."
    )
    unchanged(
        Workspace(
            desktop=[link("io.bithead.settings", "Settings")],
            dock=current.dock
        ),
        "A system application cannot be placed on the workspace."
    )
    unchanged(
        Workspace(
            desktop=[link("io.bithead.wordy"), link("io.bithead.wordy")],
            dock=current.dock
        ),
        "That application is already on the desktop."
    )
    unchanged(
        Workspace(
            desktop=[link("  ")],
            dock=current.dock
        ),
        "An application is required."
    )
