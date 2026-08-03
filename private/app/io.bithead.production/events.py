#
# Production — notification events
#
# Wraps `lib.server.send_events` so a route names an event rather than
# assembling a payload.
#
# Routes emit, not business rules: `send_events` needs the FastAPI request to
# carry the caller's credentials, and threading a request into `lib.py` would
# make every rule untestable. A route calls its rule, then announces the result.
#
# A failed notification is logged and swallowed. The work has already been
# committed by the time the event is sent, and an operator's tap must not fail
# because a dashboard did not hear about it.
#

import logging

from typing import Any, Dict, List

from lib.server import send_events

from . import db
from .lib import LIVE_STATES

LINE_STATUS = "io.bithead.production.line-status"
WORK_UNIT = "io.bithead.production.work-unit"
JOB_STATUS = "io.bithead.production.job-status"
OPERATION = "io.bithead.production.operation"


async def send(request, name: str, data: Dict[str, Any], user_ids: List[int]):
    """Announce `name` to everyone in `user_ids`, ignoring duplicates."""
    recipients = sorted({int(user_id) for user_id in user_ids if user_id is not None})
    if not recipients:
        return
    # Every value crosses the wire as a string.
    payload = {key: ("" if value is None else str(value)) for key, value in (data or {}).items()}
    try:
        await send_events(request, name, payload, recipients)
    except Exception as error:
        logging.warning(f"Production could not send event ({name}): {error}")


def admins() -> List[int]:
    """BOSS user ids that should receive admin-facing events.

    Admin is the BOSS super user, which is user 1. Kept as a function so
    widening the definition later is one edit rather than a search.
    """
    return [1]


def line_recipients(job_id: int) -> List[int]:
    """Every operator holding a live line on a job."""
    return [row["user_id"] for row in db.get_live_line_user_ids(job_id, LIVE_STATES)]


def everyone(job_id: int) -> List[int]:
    """Operators on a job and the admins watching it."""
    return line_recipients(job_id) + admins()
