#
# Production — notification events
#
# Wraps `lib.server.send_events` so business rules name an event rather than
# assembling a payload. Stage 4 fills these in.
#

from typing import Any, Dict, List

LINE_STATUS = "io.bithead.production.line-status"
WORK_UNIT = "io.bithead.production.work-unit"
JOB_STATUS = "io.bithead.production.job-status"
OPERATION = "io.bithead.production.operation"


def send(name: str, data: Dict[str, str], user_ids: List[int]):
    raise NotImplementedError


def admins() -> List[int]:
    """BOSS user ids that should receive admin-facing events."""
    raise NotImplementedError


def line_recipients(job_id: int) -> List[int]:
    """Every operator holding a live line on a job."""
    raise NotImplementedError
