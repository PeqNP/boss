#
# Where an app's files live.
#
# Every app has two directories under `media_path`:
#
#     <media_path>/<bundle>/public     nginx serves these off disk
#     <media_path>/<bundle>/private    reached only through the app
#
# The visibility is a directory rather than a flag, so a file cannot be in the
# wrong one. nginx has no route into `private`, which means an app that forgets
# to check something serves nothing — where a per-request check that somebody
# forgets to write serves everything.
#
# `media_path` sits outside the repository. A working tree is one `git clean
# -xdf` from empty, and gitignored files are exactly what that removes.
#
# A private file is handed to nginx with `X-Accel-Redirect` once the app has
# authorised it: the app decides, nginx reads, and the bytes never pass through
# Python. That header is only honoured by nginx, so private media is exercised
# through `https://localhost` rather than against port 8082 directly.
#
# Authorising is the app's — only it knows that a document belongs to one
# customer and their operator. Everything else is here.
#
# `store_public` and `store_private` are separate calls rather than one taking
# a visibility, so a call site says which it is and a wrong constant has
# nowhere to be passed.
#

import os

from dataclasses import dataclass
from typing import Optional

from fastapi import Response

from . import get_config

PUBLIC = "public"
PRIVATE = "private"

# What nginx answers `/media/...` from, and the internal location it serves a
# private file through. Both are declared in `private/nginx.conf`.
PUBLIC_URL_PREFIX = "/media"
INTERNAL_URL_PREFIX = "/_media"


# An icon is drawn a few dozen pixels wide. A megabyte is already generous,
# and the cap is here rather than in one app so every app gets the same answer.
MAX_ICON_BYTES = 1024 * 1024

# The kinds a browser draws. SVG is included and served under a sandbox policy
# — see `private/nginx.conf` — because it is XML the browser would otherwise
# execute when the file is opened directly.
IMAGE_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp")


class NotAnImage(Exception):
    """A file that is not one a browser draws."""


class TooLarge(Exception):
    """More bytes than the kind of file has cause to be."""


class NotFound(Exception):
    """No such file under the bundle's own directory."""


@dataclass
class Stored:
    """A file that has been written.

    `url` is what a client loads a public file with, and `store_private`
    leaves it unset: a private file is handed out by a route of the app's own,
    having decided who may have it.
    """
    name: str
    path: str
    url: Optional[str] = None


def _root() -> str:
    return get_config().media_path


def _directory(bundle: str, visibility: str) -> str:
    """The bundle's directory for files of that visibility, created."""
    path = os.path.join(_root(), bundle, visibility)
    os.makedirs(path, exist_ok=True)
    return path


def public_url(bundle: str, filename: str) -> str:
    """Where a stored public file is served from.

    The one place the layout is written down. A caller building the path from
    the parts would be a second copy of it, and the copy is what drifts when
    the layout moves.
    """
    return f"{PUBLIC_URL_PREFIX}/{bundle}/{PUBLIC}/{filename}"


def public_directory(bundle: str) -> str:
    """Where the bundle's world-readable files are."""
    return _directory(bundle, PUBLIC)


def private_directory(bundle: str) -> str:
    """Where the bundle's own files are."""
    return _directory(bundle, PRIVATE)


def _write(into: str, filename: str, content: bytes) -> tuple:
    """Write the bytes under a name of our own making.

    The stored name is generated rather than reusing the one it arrived with:
    two people upload `logo.png`, and both files are wanted. It also means the
    caller's name never becomes a path — the extension is all that survives.
    """
    extension = os.path.splitext(os.path.basename(filename or ""))[1].lower()
    name = f"{os.urandom(8).hex()}{extension}"
    path = os.path.join(into, name)
    with open(path, "wb") as handle:
        handle.write(content)
    return name, path


def check_image(filename: str, content: bytes,
                limit: int = MAX_ICON_BYTES) -> None:
    """Refuse a file that is not an image, or is larger than one should be.

    Called before storing rather than after: a file that is going to be
    refused is one that should never have been written.
    """
    extension = os.path.splitext(os.path.basename(filename or ""))[1].lower()
    if extension not in IMAGE_EXTENSIONS:
        raise NotAnImage(
            f"An image is one of: {', '.join(IMAGE_EXTENSIONS)}.")
    if not content:
        raise NotAnImage("That file is empty.")
    if len(content) > limit:
        raise TooLarge(f"An image is at most {limit // 1024}KB.")


def store_public(bundle: str, filename: str, content: bytes) -> Stored:
    """Write a file the world may read, and give back the URL that loads it."""
    name, path = _write(public_directory(bundle), filename, content)
    return Stored(name=name, path=path,
                  url=public_url(bundle, name))


def store_private(bundle: str, filename: str, content: bytes) -> Stored:
    """Write a file only the app may hand out.

    No URL comes back. Reaching it is a route of the app's own, which decides
    who may have it and then calls `serve_private`.
    """
    name, path = _write(private_directory(bundle), filename, content)
    return Stored(name=name, path=path)


def _inside(bundle: str, visibility: str, name: str) -> str:
    """The path a name resolves to, once it is known to be under the bundle.

    A name arriving from a request is a name and never a path. Resolving it
    and comparing against the directory is what settles that, rather than
    looking for `..` — there are more ways to write it than to list.
    """
    into = _directory(bundle, visibility)
    resolved = os.path.realpath(os.path.join(into, name))
    if os.path.commonpath([resolved, os.path.realpath(into)]) != os.path.realpath(into):
        raise NotFound(f"No such file ({name}).")
    if not os.path.isfile(resolved):
        raise NotFound(f"No such file ({name}).")
    return resolved


def serve_private(bundle: str, name: str) -> Response:
    """Hand a private file to nginx, the app having decided it may go.

    Call this *after* authorising. It confirms the file is the bundle's own
    and nothing else — the caller is what decides who may read it.
    """
    _inside(bundle, PRIVATE, name)
    return Response(
        status_code=200,
        headers={
            "X-Accel-Redirect": f"{INTERNAL_URL_PREFIX}/{bundle}/{PRIVATE}/{name}",
            # nginx supplies the rest. Sending a type here would override what
            # it works out from the file itself.
            "Content-Type": "",
        },
    )
