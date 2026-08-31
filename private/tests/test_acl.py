#
# Declaring which roles reach a route.
#
# A route names its feature and the roles that reach it on the same decorator,
# so there is nothing held apart to keep in step. An app's roles are whatever
# its routes name, accumulated as the module imports and sent to BOSS with its
# features.
#

import pytest

from enum import Enum

from lib import server
from lib.server import register_acl, require_acl


class Role(str, Enum):
    """What an app declares. The value is the label Settings shows."""
    OPERATOR = "Operator"
    EMPLOYEE = "Employee"


BUNDLE = "io.bithead.example"


@pytest.fixture(autouse=True)
def registry():
    """Each test sees an empty registry."""
    server.REGISTERED_APPS.clear()
    yield server.REGISTERED_APPS
    server.REGISTERED_APPS.clear()


def test_register_acl(registry):
    """A feature reaches the catalogue whether or not roles name it."""
    register_acl(BUNDLE, "job.r")

    app = registry[BUNDLE]
    assert app.bundleId == BUNDLE
    assert app.features == ["job.r"]
    assert app.roles == {}, "it: has the roles its routes name, and no others"


def test_register_acl_roles(registry):
    """A role holds the features named beside it."""
    register_acl(BUNDLE, "job.r", ["Operator", "Employee"])
    register_acl(BUNDLE, "job.w", ["Operator"])

    app = registry[BUNDLE]
    assert app.features == ["job.r", "job.w"]
    assert app.roles == {
        "Operator": ["job.r", "job.w"],
        "Employee": ["job.r"],
    }, "it: is the union of what every route named"


def test_register_acl_without_a_feature(registry):
    """An app registers itself even where a route names no feature."""
    register_acl(BUNDLE, None)

    assert registry[BUNDLE].features == []
    assert registry[BUNDLE].roles == {}


def test_require_acl_roles(registry):
    """The decorator takes enum members and registers their values."""

    @require_acl("job.r", roles=[Role.OPERATOR, Role.EMPLOYEE])
    async def read(request):
        return None

    app = registry[read.__module__]
    assert app.features == ["job.r"]
    assert sorted(app.roles) == ["Employee", "Operator"], \
        "it: registers the label, which is what Settings shows"

    # describe: a role that is not an enum member
    with pytest.raises(TypeError):
        @require_acl("job.w", roles=["Operator"])
        async def write(request):
            return None

    # describe: naming the role BOSS supplies
    class Reserved(str, Enum):
        DEFAULT = "default"

    with pytest.raises(ValueError):
        @require_acl("job.x", roles=[Reserved.DEFAULT])
        async def reserved(request):
            return None

    # describe: a route naming no roles at all
    @require_acl("job.d")
    async def delete(request):
        return None

    assert "job.d" in registry[delete.__module__].features


# --- Granting from an app -------------------------------------------------
#
# An app grants its own license and its own roles. The bundle comes from the
# module that called, so there is no argument to get wrong.


def test_calling_bundle():
    """Which app a call came from, read off the caller's module."""
    assert server.calling_bundle("io.bithead.scheduler") == "io.bithead.scheduler"
    assert server.calling_bundle("io.bithead.scheduler.lib") == "io.bithead.scheduler"
    assert server.calling_bundle("io.bithead.scheduler.lib.jobs") == "io.bithead.scheduler"

    # describe: a module that is not an app
    assert server.calling_bundle("lib.server") is None
    assert server.calling_bundle("__main__") is None
    assert server.calling_bundle("") is None
    assert server.calling_bundle("a.b.c") is None, \
        "it: is an installed app or nothing"


@pytest.mark.asyncio
async def test_grant_license(mocker):
    """An app gives its own license to a user."""
    post = mocker.patch.object(server, "_post_to_boss", autospec=True)
    mocker.patch.object(server, "calling_bundle", return_value=BUNDLE)

    await server.grant_license(42)

    path, body = post.call_args[0]
    assert path == "/private/acl/license"
    assert body == {"bundleId": BUNDLE, "userId": 42}, \
        "it: names the app that called, and never takes one"

    # describe: called from outside an app
    mocker.patch.object(server, "calling_bundle", return_value=None)
    with pytest.raises(ValueError):
        await server.grant_license(42)


@pytest.mark.asyncio
async def test_grant_role(mocker):
    """An app gives one of its own roles to a user."""
    post = mocker.patch.object(server, "_post_to_boss", autospec=True)
    mocker.patch.object(server, "calling_bundle", return_value=BUNDLE)

    await server.grant_role(42, Role.OPERATOR)

    path, body = post.call_args[0]
    assert path == "/private/acl/role"
    assert body["role"] == "Operator", "it: sends the label, which is the name BOSS stored"
    assert body["userId"] == 42
    assert body["revoke"] is False

    # describe: taking it away
    await server.revoke_role(42, Role.OPERATOR)
    assert post.call_args[0][1]["revoke"] is True

    # describe: a role that is not an enum member
    with pytest.raises(TypeError):
        await server.grant_role(42, "Operator")

    # describe: the role BOSS supplies
    class Reserved(str, Enum):
        DEFAULT = "default"

    with pytest.raises(ValueError):
        await server.grant_role(42, Reserved.DEFAULT)
