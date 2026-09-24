#
# System fonts the OS font picker offers.
#
# Code, not a table. Chicago and Geneva are the two BOSS already draws with.
# A later face is a file under /boss/ and a row here.
#

from typing import List, Tuple

from .model import SystemFont, SystemFonts


WEIGHTS: Tuple[str, ...] = ("regular", "bold", "italic", "boldItalic")


_FONTS = (
    SystemFont(id="ChicagoFLF", name="Chicago", styles=list(WEIGHTS)),
    SystemFont(id="Geneva", name="Geneva", styles=list(WEIGHTS)),
)


def get_system_fonts() -> List[SystemFont]:
    """Chicago and Geneva, as the font picker lists them."""
    return list(_FONTS)


def system_font_ids() -> Tuple[str, ...]:
    return tuple(font.id for font in _FONTS)
