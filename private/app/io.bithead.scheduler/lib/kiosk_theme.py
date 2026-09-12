#
# Scheduler — how a kiosk looks.
#
# Named tokens, not a generated stylesheet. Empty cells keep the BOSS
# default. Uploaded fonts are this business's; Chicago and Geneva are the
# system's.
#

import json
import os
import re

from typing import Dict, List, Optional

from lib import media

from .. import db
from ..model import KioskFont, KioskTokenStyle
from .exception import ValidationError

BUNDLE = "io.bithead.scheduler"

DEFAULT_TAG_LINE = "What can we help you with?"

SYSTEM_FONTS = ("ChicagoFLF", "Geneva")

TOKENS = (
    "background",
    "title",
    "subtitle",
    "heading",
    "body",
    "selected",
    "button-primary",
    "button-default",
    "footer",
)

COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def resolved_tag_line(stored: Optional[str]) -> str:
    """What the first booking step shows."""
    text = (stored or "").strip()
    return text if text else DEFAULT_TAG_LINE


def logo_url(filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    return media.public_url(BUNDLE, filename)


def parse_theme(stored: Optional[str]) -> Dict[str, KioskTokenStyle]:
    if not stored:
        return {}
    try:
        raw = json.loads(stored)
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    theme = {}
    for token, spec in raw.items():
        if token not in TOKENS or not isinstance(spec, dict):
            continue
        style = KioskTokenStyle(
            font=spec.get("font") or None,
            size=spec.get("size"),
            color=spec.get("color") or None
        )
        if style.font or style.size or style.color:
            theme[token] = style
    return theme


def encode_theme(theme: Dict[str, KioskTokenStyle]) -> Optional[str]:
    """JSON for storage, or None when every token is empty."""
    packed = {}
    for token, style in (theme or {}).items():
        if token not in TOKENS:
            raise ValidationError(f"Not a kiosk token: {token}.")
        spec = {}
        if style.font:
            spec["font"] = style.font
        if style.size is not None:
            spec["size"] = style.size
        if style.color:
            spec["color"] = style.color
        if spec:
            packed[token] = spec
    return json.dumps(packed) if packed else None


def check_token_style(
    style: KioskTokenStyle,
    families: Optional[List[str]] = None
) -> None:
    allowed = set(SYSTEM_FONTS) | set(families or [])
    if style.font and style.font not in allowed:
        raise ValidationError("That font is not one this business may use.")
    if style.size is not None and (style.size < 8 or style.size > 96):
        raise ValidationError("A size is between 8 and 96 pixels.")
    if style.color and COLOR.match(style.color) is None:
        raise ValidationError("A color is a six-digit hex value.")


def _font(row: "db.BusinessFontRow") -> KioskFont:
    return KioskFont(
        id=row.id,
        family=row.family,
        url=media.public_url(BUNDLE, row.filename)
    )


def get_business_fonts(business_id: int) -> List[KioskFont]:
    return [_font(r) for r in db.get_business_fonts(business_id)]


def _family_name(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or ""))[0].strip()
    cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", stem).strip()
    return cleaned or "Custom"


def add_business_font(
    business_id: int,
    filename: str,
    content: bytes
) -> KioskFont:
    if db.get_business_config(business_id) is None:
        raise ValidationError("That business no longer exists.")
    try:
        media.check_font(filename, content)
    except (media.NotAFont, media.TooLarge) as e:
        raise ValidationError(str(e))
    stored = media.store_public(BUNDLE, filename, content)
    family = _family_name(filename)
    return _font(db.get_business_font(
        db.insert_business_font(business_id, stored.name, family)
    ))


def delete_business_font(business_id: int, font_id: int) -> None:
    row = db.get_business_font(font_id)
    if row is None or row.business_id != business_id:
        raise ValidationError("That font is not this business's to remove.")
    db.delete_business_font(font_id)
    path = os.path.join(media.public_directory(BUNDLE), row.filename)
    if os.path.isfile(path):
        os.unlink(path)


def set_business_logo(business_id: int, filename: str, content: bytes) -> str:
    if db.get_business_config(business_id) is None:
        raise ValidationError("That business no longer exists.")
    current = db.get_business_config(business_id)
    try:
        media.check_image(filename, content)
    except (media.NotAnImage, media.TooLarge) as e:
        raise ValidationError(str(e))
    stored = media.store_public(BUNDLE, filename, content)
    db.set_business_logo(business_id, stored.name)
    if current.logo_filename:
        old = os.path.join(
            media.public_directory(BUNDLE),
            current.logo_filename
        )
        if os.path.isfile(old):
            os.unlink(old)
    return stored.url


def clear_business_logo(business_id: int) -> None:
    current = db.get_business_config(business_id)
    if current is None:
        raise ValidationError("That business no longer exists.")
    db.set_business_logo(business_id, None)
    if current.logo_filename:
        path = os.path.join(
            media.public_directory(BUNDLE),
            current.logo_filename
        )
        if os.path.isfile(path):
            os.unlink(path)
