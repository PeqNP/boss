#
# Where an app's files live, and which of them the world may read.
#
# The helper is generic, so it is exercised against a temporary root rather
# than the configured one.
#

import os
import tempfile

import pytest

from lib import media


BUNDLE = "io.bithead.example"


@pytest.fixture
def root(monkeypatch):
    directory = tempfile.mkdtemp()
    monkeypatch.setattr(media, "_root", lambda: directory)
    yield directory


def test_where_a_public_file_goes(root):
    """The visibility is a directory, so a file cannot be in the wrong one."""
    path = media.public_directory(BUNDLE)

    assert path == os.path.join(root, BUNDLE, "public")
    assert os.path.isdir(path), "it: is created on being asked for"


def test_where_a_private_file_goes(root):
    """The other half of the same split."""
    path = media.private_directory(BUNDLE)

    assert path == os.path.join(root, BUNDLE, "private")
    assert os.path.isdir(path)


def test_storing_a_public_file(root):
    """What is written, and what the client is given to load it with."""
    stored = media.store_public(BUNDLE, "icon.png", b"PNG")

    assert stored.url == f"/media/{BUNDLE}/public/{stored.name}", \
        "it: hands back a URL nginx serves off disk"
    assert stored.name.endswith(".png"), "it: keeps the kind of file it is"
    assert stored.name != "icon.png", \
        "it: names it uniquely, so two uploads of one name both survive"

    on_disk = os.path.join(root, BUNDLE, "public", stored.name)
    assert open(on_disk, "rb").read() == b"PNG"


def test_storing_a_private_file(root):
    """A private file has no URL of its own — the app hands it out."""
    stored = media.store_private(BUNDLE, "contract.pdf", b"PDF")

    assert stored.url is None, \
        "it: is reached through the app, which decides who may have it"
    assert os.path.isfile(os.path.join(root, BUNDLE, "private", stored.name))


def test_two_files_of_one_name(root):
    """Both survive, which is what the unique name is for."""
    first = media.store_public(BUNDLE, "logo.svg", b"<svg/>")
    second = media.store_public(BUNDLE, "logo.svg", b"<svg/>")

    assert first.name != second.name
    assert len(os.listdir(os.path.join(root, BUNDLE, "public"))) == 2


def test_a_name_that_climbs_out(root):
    """A filename is a name, and never a path."""
    stored = media.store_public(BUNDLE, "../../escape.png", b"PNG")

    on_disk = os.path.join(root, BUNDLE, "public", stored.name)
    assert os.path.isfile(on_disk), "it: lands inside the bundle's own directory"
    assert ".." not in stored.name


def test_serving_a_private_file(root):
    """nginx does the reading, once the app has said yes."""
    stored = media.store_private(BUNDLE, "contract.pdf", b"PDF")

    response = media.serve_private(BUNDLE, stored.name)

    assert response.headers["X-Accel-Redirect"] == \
        f"/_media/{BUNDLE}/private/{stored.name}", \
        "it: names the internal location, and sends no bytes itself"
    assert response.body == b"", "it: leaves the file to nginx"


def test_serving_a_private_file_that_is_not_there(root):
    """A name nobody stored."""
    with pytest.raises(media.NotFound):
        media.serve_private(BUNDLE, "nothing.pdf")


def test_serving_a_name_that_climbs_out(root):
    """The one place a caller could reach another bundle's files."""
    media.store_private(BUNDLE, "kept.pdf", b"PDF")

    for asked in ("../public/kept.pdf", "../../other/private/kept.pdf",
                  "/etc/passwd"):
        with pytest.raises(media.NotFound):
            media.serve_private(BUNDLE, asked)
