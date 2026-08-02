#
# Production — business rules
#
# The only module tests import for behaviour. Everything here takes and returns
# plain values; SQL lives in `db.py`. Every state-changing function emits its
# event through `events.py` before returning.
#
# Stage 4 fills these in. The signatures are the contract Stage 3's tests were
# written against.
#

from typing import Any, Dict, List, Optional


class Blocked(Exception):
    """A rule refused an operation, and names what stands in the way.

    Raised rather than returned so a caller cannot ignore it: deleting a pool a
    production line still requires, renaming one a historical version depends
    on, starting a job with no work units.
    """

    def __init__(self, reason: str, blockers: Optional[List[str]] = None):
        super().__init__(reason)
        self.reason = reason
        self.blockers = blockers or []


class ValidationError(Exception):
    """Input that cannot be accepted, with a message meant for the operator."""


# --- Roles ---------------------------------------------------------------

def is_admin(user) -> bool:
    raise NotImplementedError


# --- Production lines ----------------------------------------------------

def editable_version(production_line_id: int) -> int:
    """Return the version id to write to, forking the current one if frozen.

    A fork deep-copies columns, pools, operations, sections, and options, and
    duplicates each image section's file on disk so every version owns its
    images outright. Callers report `forked` to the client so it reloads —
    operation and section ids change.
    """
    raise NotImplementedError


def validate_line(version_id: int) -> List[Any]:
    """Every token error in a version. Empty means the line may be saved."""
    raise NotImplementedError


def save_production_line(user, line_id, name, columns, pool_ids) -> Dict[str, Any]:
    raise NotImplementedError


def delete_production_line(user, line_id):
    """Raises `Blocked` while any job references the line."""
    raise NotImplementedError


# --- Pools ---------------------------------------------------------------

def rename_pool(user, pool_id, name) -> Dict[str, Any]:
    """Raises `Blocked` if any line version — current or historical — uses it."""
    raise NotImplementedError


def delete_pool(user, pool_id):
    """Raises `Blocked` if referenced, or if a resource is checked out."""
    raise NotImplementedError


def return_resource(user, resource_id):
    """Force a held resource back into its pool."""
    raise NotImplementedError


# --- Jobs ----------------------------------------------------------------

def start_job(user, job_id) -> Dict[str, Any]:
    """Activate a job, pinning and freezing its production line version."""
    raise NotImplementedError


def stop_job(user, job_id) -> Dict[str, Any]:
    """Deactivate a job and pause every live line on it, origin `admin`."""
    raise NotImplementedError


def save_job(user, job_id, name, production_line_id, scheduled_start,
             scheduled_completion) -> Dict[str, Any]:
    """Create or update a job. `job_id` of `None` creates.

    Raises `ValidationError` when the completion date precedes the start.
    """
    raise NotImplementedError


def delete_job(user, job_id):
    """Raises `Blocked` while active, or once a unit is complete or failed."""
    raise NotImplementedError


def maybe_deactivate_job(job_id) -> bool:
    """Deactivate once every work unit is resolved. Called after each resolve."""
    raise NotImplementedError


def requeue_work_unit(user, work_unit_id) -> Dict[str, Any]:
    """Clear a failed unit's progress and return it to the front of the queue."""
    raise NotImplementedError


def job_throughput(job_id, window_minutes: int = 60) -> Dict[str, Any]:
    """Units per hour and average cycle time over a trailing window.

    Both are `None` when no unit completed inside it.
    """
    raise NotImplementedError


# --- Lines ---------------------------------------------------------------

def join_line(user, job_id, resources) -> Dict[str, Any]:
    """Create or resume the caller's line, checking out one resource per pool."""
    raise NotImplementedError


def leave_line(actor, line_id) -> Dict[str, Any]:
    """Release the work unit, return the resources, end the line.

    `actor` may be the operator or an admin acting from the dashboard.
    """
    raise NotImplementedError


def set_line_state(actor, line_id, state, origin, reason=None) -> Dict[str, Any]:
    """Move a line between working, paused, and stopped.

    Only the origin that raised a block may clear it — an operator cannot
    resume a line their manager stopped.
    """
    raise NotImplementedError


# --- Work ----------------------------------------------------------------

def pull_work_unit(user, line_id) -> Optional[Dict[str, Any]]:
    """Claim the next queued unit, or `None` when nothing is available."""
    raise NotImplementedError


def complete_operation(user, work_unit_id, step, values, notes) -> Dict[str, Any]:
    raise NotImplementedError


def fail_operation(user, work_unit_id, step, values, notes) -> Dict[str, Any]:
    """Fail the unit at `step`. Notes are required."""
    raise NotImplementedError


def edit_operation(user, work_unit_id, step, values, notes) -> Dict[str, Any]:
    """Change a completed step, resetting every later step."""
    raise NotImplementedError


def build_context(work_unit_id, line_id) -> Dict[str, Any]:
    """Interpolation context: work unit columns, captured values, pool values."""
    raise NotImplementedError
