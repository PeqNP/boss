#
# Scheduler — the kinds of contact detail a job type may ask a customer for.
#
# These are code, not rows. Changing one is an edit here, not a database
# update. The ids are fixed so a job type that recorded which field it asks
# for still names the same one after a restart.
#

from typing import Dict, List, Optional

from ..model import ContactFieldType


# The widgets a kiosk field knows how to draw.
FIELD_WIDGETS = ("text", "phone", "email", "address_line",
                 "city", "state", "zip")

FULL_NAME_ID = 1
PHONE_ID = 2
EMAIL_ID = 3


CONTACT_FIELDS = [
    ContactFieldType(id=FULL_NAME_ID, name="Full Name",
                     fieldType="text", otpCapable=False, sortOrder=1),
    ContactFieldType(id=PHONE_ID, name="Phone",
                     fieldType="phone", otpCapable=True, sortOrder=2),
    ContactFieldType(id=EMAIL_ID, name="Email",
                     fieldType="email", otpCapable=True, sortOrder=3),
    ContactFieldType(id=4, name="Address Line 1",
                     fieldType="address_line", otpCapable=False, sortOrder=4),
    ContactFieldType(id=5, name="Address Line 2",
                     fieldType="address_line", otpCapable=False, sortOrder=5),
    ContactFieldType(id=6, name="City",
                     fieldType="city", otpCapable=False, sortOrder=6),
    ContactFieldType(id=7, name="State",
                     fieldType="state", otpCapable=False, sortOrder=7),
    ContactFieldType(id=8, name="Zip",
                     fieldType="zip", otpCapable=False, sortOrder=8),
]


def get_contact_field_types() -> List[ContactFieldType]:
    """The kinds of contact information a job type may ask a customer for."""
    return list(CONTACT_FIELDS)


def get_contact_field_type(field_id: int) -> Optional[ContactFieldType]:
    """One catalog entry, or nothing if that id is not in the catalog."""
    for field in CONTACT_FIELDS:
        if field.id == field_id:
            return field
    return None


def get_contact_field_type_by_name(name: str) -> Optional[ContactFieldType]:
    """One catalog entry by the name a booking form or a test keys on."""
    for field in CONTACT_FIELDS:
        if field.name == name:
            return field
    return None


def typed_contact(rows) -> Dict[str, str]:
    """Job contact rows keyed by catalog name.

    `rows` carry `contact_field_type_id` and `value`. Unknown ids are skipped.
    """
    typed = {}
    for row in rows:
        field = get_contact_field_type(row.contact_field_type_id)
        if field is None:
            continue
        typed[field.name] = row.value
    return typed
