#
# Scheduler — the kinds of business an operator may start from.
#
# These are code, not rows. Changing one is an edit here, not a database
# update. The ids are fixed so a business that recorded which type it chose
# still names the same one after a restart.
#

from typing import List, Optional

from ..model import BusinessTemplate


BUSINESS_TEMPLATES = [
    BusinessTemplate(
        id=1,
        name="Personal Service",
        description=(
            "Salons, spas, fitness studios. Clients choose their service "
            "provider."
        ),
        config={
            "allowCustomerEmployeeSelection": True,
            "slotIncrementMinutes": 15,
        },
    ),
    BusinessTemplate(
        id=2,
        name="Field Service",
        description=(
            "Landscaping, cleaning, home repair. Technicians go to the "
            "customer."
        ),
        config={
            "notifyEmployees": True,
            "bufferMinutes": 30,
            "slotIncrementMinutes": 30,
        },
    ),
    BusinessTemplate(
        id=3,
        name="Healthcare/Wellness",
        description=(
            "Dental, chiropractic, therapy. Privacy and verification matter."
        ),
        config={
            "slotIncrementMinutes": 15,
            "bufferMinutes": 15,
        },
    ),
    BusinessTemplate(
        id=4,
        name="Pet Services",
        description=(
            "Grooming, walking, sitting. Mix of at-location and field visits."
        ),
        config={
            "allowCustomerEmployeeSelection": True,
            "bufferMinutes": 15,
        },
    ),
    BusinessTemplate(
        id=5,
        name="General",
        description="A flexible starting point for any service business.",
        config={},
    ),
    BusinessTemplate(
        id=6,
        name="Food & Drink",
        description=(
            "Cafés, bakeries, takeaway. Customers choose a pickup time and "
            "you handle the queue."
        ),
        config={
            "slotMode": "unlimited",
            "minBookingNoticeHours": 0,
            "bufferMinutes": 0,
        },
    ),
]


def get_business_templates() -> List[BusinessTemplate]:
    """Starting points a new business may take its settings from."""
    return list(BUSINESS_TEMPLATES)


def get_business_template(template_id: int) -> Optional[BusinessTemplate]:
    """One starting point, or nothing if that id is not in the catalog."""
    for template in BUSINESS_TEMPLATES:
        if template.id == template_id:
            return template
    return None
