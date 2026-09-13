#!/usr/bin/env python3
#
# BOSS private service — system catalog.
#

from libtest import *

get_app_module("io.bithead.boss")
from io.bithead.boss.fonts import get_system_fonts, system_font_ids


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
