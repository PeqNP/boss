#
# Scheduler — the records the platform keeps, and every business draws from.
#
# Holidays, business templates, contact field types, vendors, the hold timeout,
# and the system icon set: one copy each, maintained by whoever runs the
# platform and chosen from by every business on it.
#
# A business never edits these. It picks from them, and what it picks is stored
# against the business.
#

import json
import os

from typing import List, Optional

from lib import media

from .. import db
from ..model import *
from .business import get_business_config, update_business_config
from .exception import ValidationError

# What each kind of service may be set to. A vendor absent here is one nothing
# knows how to reach.
REGISTERED_VENDORS = {
    "email": ("sendgrid", "mailgun"),
    "sms": ("twilio",),
    "payment": ("stripe",),
}


BUNDLE = "io.bithead.scheduler"


# Where the bundle keeps the icons it ships. `img` is what every bundle calls
# the directory, so the URL is worked out from the filename rather than stored.
SYSTEM_ICON_URL = f"/boss/app/{BUNDLE}/img"


ICON_KINDS = ("system", "custom")


def _icon(row: "db.IconRow") -> Icon:
    return Icon(
        id=row.id,
        filename=row.filename,
        isSystem=bool(row.is_system),
        url=(f"{SYSTEM_ICON_URL}/{row.filename}" if row.is_system
             else media.public_url(BUNDLE, row.filename)),
    )


def get_icons(business_id: int, kind: str) -> List[Icon]:
    """The icons a business may choose from, of one kind."""
    if kind not in ICON_KINDS:
        raise ValidationError(f"An icon is {' or '.join(ICON_KINDS)}.")
    rows = (db.get_system_icons() if kind == "system"
            else db.get_business_icons(business_id))
    return [_icon(r) for r in rows]


def add_system_icon(filename: str) -> Icon:
    """Record an icon the app bundle ships.

    The file is in the bundle already; this is the row a job type points at.
    """
    if not filename.strip():
        raise ValidationError("Please name the icon.")
    return _icon(db.get_icon(db.insert_icon(None, filename.strip(), 1)))


def add_icon(business_id: int, filename: str, content: bytes) -> Icon:
    """Store a business's own icon.

    Checked before it is written: a file that is going to be refused is one
    that should never have reached the disk.
    """
    try:
        media.check_image(filename, content)
    except (media.NotAnImage, media.TooLarge) as e:
        raise ValidationError(str(e))

    stored = media.store_public(BUNDLE, filename, content)
    return _icon(db.get_icon(db.insert_icon(business_id, stored.name, 0)))


def delete_icon(business_id: int, icon_id: int) -> None:
    """Remove a business's own icon.

    A system icon stays: it belongs to no business — `business_id` is null —
    so it matches nobody's claim to it, and one business removing it would
    take it from all the others.
    """
    row = db.get_icon(icon_id)
    if row is None or row.business_id != business_id:
        raise ValidationError("That icon is not this business's to remove.")
    db.delete_icon(icon_id)
    path = os.path.join(media.public_directory(BUNDLE), row.filename)
    if os.path.isfile(path):
        os.unlink(path)


def get_holiday_years() -> List[int]:
    """The years the platform has holidays for."""
    return db.get_holiday_years()


def get_platform_holidays(year: int) -> SystemHolidays:
    """Every holiday in a year, grouped by the country it belongs to."""
    countries: Dict[str, Country] = {}
    for row in db.get_holidays_for_year(year):
        country = countries.get(row.country_code)
        if country is None:
            country = Country(
                countryCode=row.country_code,
                countryName=row.country_name,
                holidays=[]
            )
            countries[row.country_code] = country
        country.holidays.append(
            CountryHoliday(id=row.id, name=row.name, date=row.date))
    return SystemHolidays(year=year, countries=list(countries.values()))


def _check_template(
    name: str,
    description: str,
    template_id: Optional[int] = None
) -> None:
    if not name.strip():
        raise ValidationError("Please name the template.")
    if not description.strip():
        raise ValidationError("Please describe what this template is for.")
    for existing in db.get_business_templates():
        if existing.name.lower() == name.strip().lower() \
                and existing.id != template_id:
            raise ValidationError(f"There is already a {existing.name} template.")


def add_business_template(
    name: str,
    description: str,
    config: Optional[dict] = None
) -> BusinessTemplate:
    """Offer a new starting point.

    `config` holds only the settings the template has an opinion about;
    everything it leaves out keeps whatever the business already had.
    """
    _check_template(name, description)
    template_id = db.insert_business_template(
        name.strip(),
        description.strip(),
        json.dumps(config or {})
    )
    return [t for t in get_business_templates() if t.id == template_id][0]


def update_business_template(
    template_id: int,
    name: str,
    description: str
) -> BusinessTemplate:
    """Rename or reword one. Its settings are left as they are."""
    if db.get_business_template(template_id) is None:
        raise ValidationError("That template no longer exists.")
    _check_template(name, description, template_id)
    db.set_business_template(template_id, name.strip(), description.strip())
    return [t for t in get_business_templates() if t.id == template_id][0]


def delete_business_template(template_id: int) -> None:
    """Stop offering it. A business that took it keeps what it was given."""
    if db.get_business_template(template_id) is None:
        raise ValidationError("That template no longer exists.")
    db.delete_business_template(template_id)


BUSINESS_STATUSES = {"all": None, "active": 1, "inactive": 0}


def _platform_business(row: "db.PlatformBusinessRow") -> Optional[BusinessConfig]:
    """One business as the platform sees it: the operator's settings, and the
    two fields only the platform holds.

    The same model the operator's own window reads, so an admin helping them
    reads one shape rather than a second that overlaps it.
    """
    config = get_business_config(row.id)
    if config is None:
        return None
    config.isActive = bool(row.is_active)
    # The date alone. The screen lists when a business joined, and the hour it
    # happened is nobody's business.
    config.createDate = row.create_date[:10]
    return config


def _platform_business_row(row: "db.PlatformBusinessRow") -> PlatformBusiness:
    """A business as the platform's list shows it: enough to pick one."""
    return PlatformBusiness(
        id=row.id,
        name=row.name,
        ownerName=row.owner_name or "",
        isActive=bool(row.is_active),
        createDate=row.create_date[:10]
    )


def get_platform_businesses(status: str = "all") -> List[PlatformBusiness]:
    """Every business, or the open ones, or the closed ones."""
    if status not in BUSINESS_STATUSES:
        raise ValidationError(
            f"A status is one of: {', '.join(BUSINESS_STATUSES)}.")
    return [_platform_business_row(r)
            for r in db.get_platform_businesses(BUSINESS_STATUSES[status])]


def get_platform_business(business_id: int) -> Optional[BusinessConfig]:
    row = db.get_platform_business(business_id)
    return _platform_business(row) if row is not None else None


def update_platform_business(business_id: int, details: dict) -> BusinessConfig:
    """Change a business's record from the platform side.

    `update_business_config` is what refuses a business that is gone, and in
    the same words — this is the platform's door onto the operator's writer.
    """
    update_business_config(business_id, details)
    return get_platform_business(business_id)


def _set_active(business_id: int, active: bool) -> BusinessConfig:
    if db.get_platform_business(business_id) is None:
        raise ValidationError("That business no longer exists.")
    db.set_business_active(business_id, 1 if active else 0)
    return get_platform_business(business_id)


def enable_business(business_id: int) -> BusinessConfig:
    """Open it for business again."""
    return _set_active(business_id, True)


def disable_business(business_id: int) -> BusinessConfig:
    """Close it. The kiosk stops taking bookings; the record stays."""
    return _set_active(business_id, False)


def delete_business(business_id: int) -> None:
    """Remove a business that never traded.

    One with appointments behind it is closed rather than removed: those
    bookings are somebody's record of work done and money paid, and `disable`
    is the door for a business that is finished.
    """
    if db.get_platform_business(business_id) is None:
        raise ValidationError("That business no longer exists.")
    booked = db.count_jobs_for_business(business_id)
    if booked:
        raise ValidationError(
            f"This business has {booked} appointment(s). Close it instead.")
    db.delete_business(business_id)


# The kinds a screen knows how to draw.
CONTACT_FIELD_TYPES = ("text", "phone", "email", "address_line",
                       "city", "state", "zip")


# A code reaches a phone or an inbox, and nothing else.
OTP_REACHABLE = ("phone", "email")


def _check_contact_field_type(
    name: str,
    field_type: str,
    otp_capable: bool,
    field_id: Optional[int] = None
):
    if not name.strip():
        raise ValidationError("Please name the field.")
    if field_type not in CONTACT_FIELD_TYPES:
        raise ValidationError(
            f"A field is one of: {', '.join(CONTACT_FIELD_TYPES)}.")
    if otp_capable and field_type not in OTP_REACHABLE:
        raise ValidationError(
            f"A verification code reaches a {' or a '.join(OTP_REACHABLE)}.")

    # Two fields of the same name are two boxes a customer cannot tell apart.
    for existing in db.get_contact_field_types():
        if existing.name.lower() == name.strip().lower() \
                and existing.id != field_id:
            raise ValidationError(f"There is already a {existing.name} field.")


def add_contact_field_type(
    name: str,
    field_type: str,
    otp_capable: bool = False
) -> ContactFieldType:
    """Offer every business one more kind of detail to ask for."""
    _check_contact_field_type(name, field_type, otp_capable)
    field_id = db.insert_contact_field_type(
        name.strip(),
        field_type,
        1 if otp_capable else 0,
        db.next_contact_field_type_sort_order()
    )
    return [f for f in get_contact_field_types() if f.id == field_id][0]


def update_contact_field_type(
    field_id: int,
    name: str,
    field_type: str,
    otp_capable: bool = False
) -> ContactFieldType:
    if db.get_contact_field_type(field_id) is None:
        raise ValidationError("That field no longer exists.")
    _check_contact_field_type(name, field_type, otp_capable, field_id)
    db.set_contact_field_type(
        field_id,
        name.strip(),
        field_type,
        1 if otp_capable else 0
    )
    return [f for f in get_contact_field_types() if f.id == field_id][0]


def delete_contact_field_type(field_id: int) -> None:
    """Stop offering it.

    A field a job type is asking for stays: removing it would leave a booking
    form asking for something the platform no longer has a name for.
    """
    if db.get_contact_field_type(field_id) is None:
        raise ValidationError("That field no longer exists.")
    asking = db.count_job_types_asking_for(field_id)
    if asking:
        raise ValidationError(
            f"{asking} job type(s) ask for this field. Remove it from them first.")
    db.delete_contact_field_type(field_id)


def reorder_contact_field_types(field_ids: List[int]) -> List[ContactFieldType]:
    """Ask for them in this order, everywhere.

    The whole order arrives each time, as the job type's own reorder does.
    """
    current = [f.id for f in db.get_contact_field_types()]
    if sorted(field_ids) != sorted(current):
        raise ValidationError("That order no longer matches the fields there are.")
    for position, field_id in enumerate(field_ids):
        db.set_contact_field_type_sort_order(field_id, position)
    return get_contact_field_types()


def get_contact_field_types() -> List[ContactFieldType]:
    """The kinds of contact information a job type may ask a customer for.

    A business chooses from these rather than inventing them, which is why the
    kiosk can trust that a field marked verifiable can receive a code.
    """
    return [
        ContactFieldType(
            id=r.id,
            name=r.name,
            fieldType=r.field_type,
            otpCapable=bool(r.otp_capable),
            sortOrder=r.sort_order
        )
        for r in db.get_contact_field_types()
    ]


def get_vendors() -> List[Vendor]:
    """Every kind of outbound thing, and which service is chosen for it.

    A kind with nobody chosen is listed too — that is the screen's whole
    purpose, and a missing row reads as a kind the platform does not have.
    """
    chosen = {row.vendor_type: row for row in db.get_vendor_configs()}
    vendors = []
    for vendor_type in sorted(REGISTERED_VENDORS):
        row = chosen.get(vendor_type)
        config = json.loads(row.config_json) if row else {}
        vendors.append(Vendor(
            type=vendor_type,
            currentVendor=row.vendor_name if row else None,
            registeredVendors=list(REGISTERED_VENDORS[vendor_type]),
            configKeys=sorted(config)
        ))
    return vendors


def set_vendor(
    vendor_type: str,
    vendor_name: Optional[str],
    config: Optional[dict] = None
) -> Vendor:
    """Choose the service one kind of thing goes through.

    `vendor_name` of `None` clears the choice, which is how a super admin turns
    a kind off — the alternative is a row naming a vendor nobody wants used.
    """
    if vendor_type not in REGISTERED_VENDORS:
        raise ValidationError(
            f"The platform has no {vendor_type} vendors.")
    if vendor_name is not None and vendor_name not in REGISTERED_VENDORS[vendor_type]:
        known = ", ".join(REGISTERED_VENDORS[vendor_type])
        raise ValidationError(
            f"{vendor_name} is not a {vendor_type} vendor. Choose one of: {known}.")

    # One choice per kind, so the previous one goes before the new one lands.
    db.clear_vendor_config(vendor_type)
    if vendor_name is not None:
        db.insert_vendor_config(
            vendor_type,
            vendor_name,
            json.dumps(config or {})
        )

    return next(v for v in get_vendors() if v.type == vendor_type)


def get_business_templates() -> List[BusinessTemplate]:
    """Starting points a new business may take its settings from."""
    return [
        BusinessTemplate(
            id=r.id,
            name=r.name,
            description=r.description,
            config=json.loads(r.config_json)
        )
        for r in db.get_business_templates()
    ]


def get_schedule_timeout_minutes() -> int:
    """How long a customer has to finish scheduling before their time is released."""
    value = db.get_system_config("schedule_timeout_minutes")
    return int(value) if value is not None else 10


def set_schedule_timeout_minutes(minutes: int) -> int:
    """How long a hold lasts before the time is released.

    A hold with no end is a time nobody else can take, so there is a floor of
    one minute rather than none.
    """
    if minutes < 1:
        raise ValidationError("A hold lasts at least a minute.")
    db.set_system_config("schedule_timeout_minutes", str(minutes))
    return minutes
