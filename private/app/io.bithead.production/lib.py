#
# Production — business rules
#
# The only module tests import for behaviour. Everything here takes and returns
# plain values, and every statement it issues is a named function in `db.py`.
#
# Notifications are *not* sent from here. `lib.server.send_events` needs the
# FastAPI request to carry the caller's credentials, and threading a request
# through a business rule would make it untestable. Routes emit the event named
# in `events.py` after the rule they call returns.
#

import json
import os
import shutil

from datetime import datetime
from typing import Any, Dict, List, Optional

from . import db
from . import tokens
from .model import *

# A line that has not been left is still the operator's, whether they are
# working, on break, or blocked. These are also the only states a line may be
# set to: `left` is reached by leaving, not by a state change.
LIVE_STATES = ("working", "paused", "stopped")

# A work unit is resolved once it can no longer be worked. A failed unit counts:
# the job is finished even though not every unit succeeded.
RESOLVED_STATES = ("complete", "failed")

SECTION_TYPES = ("description", "image", "text", "number", "checkbox", "options")

# Sections that capture something. Only these carry a name, because only these
# can be addressed by a token.
INPUT_SECTION_TYPES = ("text", "number", "checkbox", "options")


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



# --- From storage --------------------------------------------------------
#
# `db.py` returns row models — how SQLite hands data back. These turn them into
# what the app means, once per shape rather than once per call site. Integers
# become booleans and a column of JSON text becomes a dict here, so nothing
# below has to remember that storage had an opinion.

def _pool(row) -> Optional[Pool]:
    return None if row is None else Pool(
        id=row.id, name=row.name, createdAt=row.created_at, createdBy=row.created_by)


def _resource(row) -> Optional[PoolResource]:
    return None if row is None else PoolResource(
        id=row.id, poolId=row.pool_id, name=row.name, value=row.value,
        inService=bool(row.in_service), heldByLineId=row.held_by_line_id,
        sortOrder=row.sort_order)


def _production_line(row) -> Optional[ProductionLine]:
    return None if row is None else ProductionLine(
        id=row.id, name=row.name, currentVersionId=row.current_version_id,
        createdAt=row.created_at, createdBy=row.created_by)


def _version(row) -> Optional[ProductionLineVersion]:
    return None if row is None else ProductionLineVersion(
        id=row.id, productionLineId=row.production_line_id, version=row.version,
        frozen=bool(row.frozen), createdAt=row.created_at)


def _column(row) -> DeclaredColumn:
    return DeclaredColumn(id=row.id, versionId=row.version_id, name=row.name,
                          sortOrder=row.sort_order)


def _required_pool(row) -> RequiredPool:
    return RequiredPool(id=row.id, versionId=row.version_id, poolId=row.pool_id,
                        poolName=row.pool_name, sortOrder=row.sort_order)


def _operation(row) -> Optional[Operation]:
    return None if row is None else Operation(
        id=row.id, versionId=row.version_id, name=row.name, step=row.step)


def _section(row) -> Optional[OperationSection]:
    return None if row is None else OperationSection(
        id=row.id, operationId=row.operation_id, sectionType=row.section_type,
        sortOrder=row.sort_order, name=row.name, label=row.label,
        required=bool(row.required), body=row.body, imagePath=row.image_path)


def _section_option(row) -> SectionOption:
    return SectionOption(id=row.id, sectionId=row.section_id, label=row.label,
                         sortOrder=row.sort_order)


def _job(row) -> Optional[Job]:
    return None if row is None else Job(
        id=row.id, name=row.name, productionLineId=row.production_line_id,
        versionId=row.version_id, scheduledStart=row.scheduled_start,
        scheduledCompletion=row.scheduled_completion, active=bool(row.active),
        createdAt=row.created_at, createdBy=row.created_by)


def _work_unit(row) -> Optional[WorkUnit]:
    return None if row is None else WorkUnit(
        id=row.id, jobId=row.job_id, rowOrder=row.row_order,
        input=json.loads(row.input_json), state=row.state,
        lineId=row.assigned_line_id, currentStep=row.current_step,
        startedAt=row.started_at, completedAt=row.completed_at,
        failedAt=row.failed_at, failedStep=row.failed_step, requeuedAt=row.requeued_at)


def _line(row) -> Optional[Line]:
    return None if row is None else Line(
        id=row.id, jobId=row.job_id, userId=row.user_id, state=row.state,
        pauseOrigin=row.pause_origin, stopOrigin=row.stop_origin,
        stopReason=row.stop_reason, unitsCompleted=row.units_completed,
        unitsFailed=row.units_failed, joinedAt=row.joined_at,
        lastActiveAt=row.last_active_at)


def _unit_operation(row) -> Optional[UnitOperation]:
    return None if row is None else UnitOperation(
        id=row.id, workUnitId=row.work_unit_id, step=row.step, state=row.state,
        notes=row.notes, startedAt=row.started_at, completedAt=row.completed_at,
        completedBy=row.completed_by)


def _captured(row) -> CapturedValue:
    return CapturedValue(step=row.step, name=row.name, value=row.value)


def _unit_edit(row) -> UnitEdit:
    return UnitEdit(id=row.id, workUnitId=row.work_unit_id, step=row.step, name=row.name,
                    oldValue=row.old_value, newValue=row.new_value, editedBy=row.edited_by,
                    editedAt=row.edited_at, stepsReset=row.steps_reset)


def _used_resource(row) -> UsedResource:
    return UsedResource(pool=row.pool_name, resource=row.resource_name,
                        value=row.resource_value)


def _line_resource(row) -> LineResource:
    return LineResource(poolId=row.pool_id, resourceId=row.resource_id,
                        poolName=row.pool_name, resourceName=row.resource_name,
                        resourceValue=row.resource_value)


def _interval(row) -> BlockingInterval:
    return BlockingInterval(startedAt=row.started_at, endedAt=row.ended_at)


def _completed_unit(row) -> CompletedUnit:
    return CompletedUnit(id=row.id, startedAt=row.started_at,
                         completedAt=row.completed_at, lineId=row.assigned_line_id)


def _pool_reference(row) -> PoolReference:
    return PoolReference(lineName=row.line_name, version=row.version)


def _held_resource(row) -> HeldResource:
    return HeldResource(resourceName=row.resource_name, userId=row.user_id)


def _live_line(row) -> LiveLine:
    return LiveLine(id=row.id, jobName=row.job_name)


def _state_count(row) -> StateCount:
    return StateCount(state=row.state, count=row.count)


def _each(converter, rows) -> List[Any]:
    return [converter(row) for row in rows]


# --- Roles ---------------------------------------------------------------

def is_admin(user) -> bool:
    """Admin is the BOSS super user, which is user 1.

    Accepts a `User` or a bare id, because rules are called from routes (which
    hold the authenticated user) and from tests (which hold an id).
    """
    return _user_id(user) == 1


def _user_id(user) -> int:
    return getattr(user, "id", user)


# --- Reading the model ---------------------------------------------------

def _require_job(job_id: int):
    job = _job(db.get_job(job_id))
    if job is None:
        raise ValidationError("That job no longer exists.")
    return job


def _require_line(line_id: int):
    line = _line(db.get_line(line_id))
    if line is None:
        raise ValidationError("That line no longer exists.")
    return line


def _require_work_unit(work_unit_id: int):
    unit = _work_unit(db.get_work_unit(work_unit_id))
    if unit is None:
        raise ValidationError("That work unit no longer exists.")
    return unit


def job_version_id(job) -> Optional[int]:
    """The version a job runs against: the one it pinned, else the current one."""
    if job.versionId is not None:
        return job.versionId
    line = _production_line(db.get_production_line(job.productionLineId))
    return line.currentVersionId if line else None


# --- Production lines ----------------------------------------------------

def _upload_dir() -> str:
    from lib.server import get_boss_path
    return os.path.join(get_boss_path(), "public", "upload", "io.bithead.production")


def _copy_image(image_path: Optional[str]) -> Optional[str]:
    """Duplicate an image section's file so the new version owns it outright.

    Sharing the file would mean deleting a section from one version silently
    breaks another. Copying costs disk and buys an unconditional delete.
    """
    if not image_path:
        return None
    directory = _upload_dir()
    name = os.path.basename(image_path)
    source = os.path.join(directory, name)
    if not os.path.isfile(source):
        # The row outlived its file. Carry the reference forward rather than
        # failing the fork: a missing image is a broken picture, not a broken
        # production line.
        return image_path
    stem, extension = os.path.splitext(name)
    copy_name = f"{stem}-{os.urandom(4).hex()}{extension}"
    shutil.copyfile(source, os.path.join(directory, copy_name))
    return f"/upload/io.bithead.production/{copy_name}"


def _create_version(production_line_id: int, version: int) -> int:
    version_id = db.insert_version(production_line_id, version)
    db.set_current_version(production_line_id, version_id)
    return version_id


def editable_version(production_line_id: int) -> int:
    """Return the version id to write to, forking the current one if frozen.

    A fork deep-copies columns, pools, operations, sections, and options, and
    duplicates each image section's file on disk so every version owns its
    images outright. Callers report `forked` to the client so it reloads —
    operation and section ids change.
    """
    line = _production_line(db.get_production_line(production_line_id))
    if line is None:
        raise ValidationError("That production line no longer exists.")

    current_id = line.currentVersionId
    if current_id is None:
        return _create_version(production_line_id, 1)

    current = _version(db.get_version(current_id))
    if not current.frozen:
        return current_id

    forked_id = _create_version(production_line_id, current.version + 1)

    for column in _each(_column, db.get_columns(current_id)):
        db.insert_column(forked_id, column.name, column.sortOrder)

    for pool in _each(_required_pool, db.get_version_pools(current_id)):
        db.insert_version_pool(forked_id, pool.poolId, pool.poolName, pool.sortOrder)

    for operation in _each(_operation, db.get_operations(current_id)):
        operation_id = db.insert_operation(forked_id, operation.name, operation.step)
        for section in _each(_section, db.get_sections(operation.id)):
            section_id = db.insert_section(
                operation_id, section.sectionType, section.sortOrder, section.name,
                section.label, section.required, section.body,
                _copy_image(section.imagePath))
            for option in _each(_section_option, db.get_section_options(section.id)):
                db.insert_section_option(section_id, option.label, option.sortOrder)

    return forked_id


def validate_line(version_id: int) -> List[Any]:
    """Every token error in a version. Empty means the line may be saved."""
    columns = [row.name for row in _each(_column, db.get_columns(version_id))]
    pools = [row.poolName for row in _each(_required_pool, db.get_version_pools(version_id))]

    errors = []
    captured: Dict[int, List[str]] = {}

    for operation in _each(_operation, db.get_operations(version_id)):
        step = operation.step
        for section in _each(_section, db.get_sections(operation.id)):
            # A description's body and an input's label are both read by the
            # operator, so both may address work captured earlier.
            for text in (section.body, section.label):
                for error in tokens.validate(text, step, columns, pools, captured):
                    error.operation_name = operation.name
                    errors.append(error)
            if section.name:
                captured.setdefault(step, []).append(section.name)

    return errors


def save_production_line(user, line_id, name, columns, pool_ids) -> SavedProductionLine:
    """Create or update a production line. `line_id` of `None` creates."""
    name = (name or "").strip()
    if not name:
        raise ValidationError("A production line needs a name.")

    created = line_id is None
    if created:
        line_id = db.insert_production_line(name, _user_id(user))
        version_id = _create_version(line_id, 1)
        forked = False
    else:
        before = _production_line(db.get_production_line(line_id))
        if before is None:
            raise ValidationError("That production line no longer exists.")
        db.set_production_line_name(line_id, name)
        version_id = editable_version(line_id)
        forked = version_id != before.currentVersionId

    db.delete_columns(version_id)
    for order, column in enumerate(columns or []):
        db.insert_column(version_id, column, order)

    db.delete_version_pools(version_id)
    for order, pool_id in enumerate(pool_ids or []):
        pool = _pool(db.get_pool(pool_id))
        if pool is None:
            raise ValidationError("One of the chosen resource pools no longer exists.")
        db.insert_version_pool(version_id, pool_id, pool.name, order)

    return SavedProductionLine(lineId=line_id, versionId=version_id, forked=forked,
                               created=created)


def delete_production_line(user, line_id):
    """Raises `Blocked` while any job references the line."""
    jobs = _each(_job, db.get_jobs_using_line(line_id))
    if jobs:
        raise Blocked("This production line cannot be deleted while jobs reference it.",
                      [row.name for row in jobs])
    db.delete_production_line(line_id)


# --- Authoring operations ------------------------------------------------

def add_operation(user, line_id, name) -> SavedOperation:
    """Append an operation to a production line, forking a frozen version."""
    name = (name or "").strip()
    if not name:
        raise ValidationError("An operation needs a name.")

    before = _production_line(db.get_production_line(line_id))
    if before is None:
        raise ValidationError("That production line no longer exists.")

    version_id = editable_version(line_id)
    step = db.get_last_step(version_id) + 1
    operation_id = db.insert_operation(version_id, name, step)
    return SavedOperation(operationId=operation_id, step=step, versionId=version_id,
                          forked=version_id != before.currentVersionId)


def _editable_operation(operation_id: int):
    """The operation to write to, forking its version first if it is frozen.

    A fork gives every operation a new id, so the caller is handed back the
    copy — and told to reload, because the id it held is now history.
    """
    operation = _operation(db.get_operation(operation_id))
    if operation is None:
        raise ValidationError("That operation no longer exists.")

    version = _version(db.get_version(operation.versionId))
    editable_id = editable_version(version.productionLineId)
    if editable_id == operation.versionId:
        return operation, False
    return _operation(db.get_operation_at(editable_id, operation.step)), True


def add_section(user, operation_id, section_type, name=None, label=None, required=False,
                body=None, options=None) -> SavedSection:
    """Append a section to an operation, forking a frozen version."""
    if section_type not in SECTION_TYPES:
        raise ValidationError(f"“{section_type}” is not a kind of section.")
    if section_type in INPUT_SECTION_TYPES and not (name or "").strip():
        raise ValidationError("An input section needs a name, which is how a token addresses it.")

    operation, forked = _editable_operation(operation_id)
    sort_order = db.count_sections(operation.id)
    section_id = db.insert_section(operation.id, section_type, sort_order,
                                   (name or "").strip() or None, label,
                                   1 if required else 0, body, None)
    for order, option in enumerate(options or []):
        db.insert_section_option(section_id, option, order)

    return SavedSection(sectionId=section_id, operationId=operation.id,
                        versionId=operation.versionId, forked=forked)


# --- Pools ---------------------------------------------------------------

def _pool_blockers(pool_id: int) -> List[str]:
    return [f"{row.lineName} (version {row.version})"
            for row in _each(_pool_reference, db.pool_references(pool_id))]


def save_pool(user, pool_id, name) -> SavedPool:
    """Create a pool, or rename one. `pool_id` of `None` creates."""
    name = (name or "").strip()
    if not name:
        raise ValidationError("A pool needs a name.")

    if pool_id is not None:
        return rename_pool(user, pool_id, name)

    if _pool(db.find_pool_named(name)):
        raise ValidationError(f"A pool named “{name}” already exists. Pool names are how tokens"
                              f" find them, so they must differ by more than capitalisation.")
    return SavedPool(poolId=db.insert_pool(name, _user_id(user)), name=name, created=True)


def rename_pool(user, pool_id, name) -> SavedPool:
    """Raises `Blocked` if any line version — current or historical — uses it."""
    name = (name or "").strip()
    if not name:
        raise ValidationError("A pool needs a name.")

    pool = _pool(db.get_pool(pool_id))
    if pool is None:
        raise ValidationError("That pool no longer exists.")

    if name.casefold() != pool.name.casefold():
        if _pool(db.find_pool_named(name, pool_id)):
            raise ValidationError(f"A pool named “{name}” already exists. Pool names are how"
                                  f" tokens find them, so they must differ by more than"
                                  f" capitalisation.")

        blockers = _pool_blockers(pool_id)
        if blockers:
            raise Blocked("This pool cannot be renamed while production lines require it."
                          " Their descriptions address it by name.", blockers)

    db.set_pool_name(pool_id, name)
    return SavedPool(poolId=pool_id, name=name)


def delete_pool(user, pool_id):
    """Raises `Blocked` if referenced, or if a resource is checked out."""
    blockers = _pool_blockers(pool_id)
    if blockers:
        raise Blocked("This pool cannot be deleted while production lines require it.", blockers)

    # Unreachable through the interface as it stands: a resource can only be
    # checked out from a pool some version requires, and that version blocks
    # the delete above. Kept as the cheaper of the two guards to be wrong about.
    held = _each(_held_resource, db.held_resources(pool_id))
    if held:
        raise Blocked("This pool cannot be deleted while its resources are checked out.",
                      [row.resourceName for row in held])

    db.delete_pool(pool_id)


def save_resource(user, pool_id, resource_id, name, value, in_service=True) -> SavedResource:
    """Create or update one resource in a pool. `resource_id` of `None` creates."""
    name = (name or "").strip()
    value = (value or "").strip()
    if not name:
        raise ValidationError("A resource needs a name.")
    if not value:
        raise ValidationError("A resource needs a value. The value is what its token renders.")

    if resource_id is None:
        if _pool(db.get_pool(pool_id)) is None:
            raise ValidationError("That pool no longer exists.")
        resource_id = db.insert_resource(pool_id, name, value, len(_each(_resource, db.get_resources(pool_id))))
        return SavedResource(resourceId=resource_id, created=True)

    if _resource(db.get_resource(resource_id)) is None:
        raise ValidationError("That resource no longer exists.")
    db.update_resource(resource_id, name, value, 1 if in_service else 0)
    return SavedResource(resourceId=resource_id, created=False)


def delete_resource(user, resource_id):
    """Raises `Blocked` while the resource is checked out to a line."""
    resource = _resource(db.get_resource(resource_id))
    if resource is None:
        raise ValidationError("That resource no longer exists.")
    if resource.heldByLineId is not None:
        raise Blocked(f"“{resource.name}” is checked out and cannot be deleted.",
                      [resource.name])
    db.delete_resource(resource_id)


def return_resource(user, resource_id) -> ReturnedResource:
    """Force a held resource back into its pool.

    The line is left alone. An admin reclaiming a card from an operator who
    walked away should not also end their line and discard their metrics.
    """
    resource = _resource(db.get_resource(resource_id))
    if resource is None:
        raise ValidationError("That resource no longer exists.")

    line_id = resource.heldByLineId
    if line_id is not None:
        db.delete_line_resource(line_id, resource_id)
    db.release_resource(resource_id)
    return ReturnedResource(resourceId=resource_id, lineId=line_id)


# --- Jobs ----------------------------------------------------------------

def start_job(user, job_id) -> StartedJob:
    """Activate a job, pinning and freezing its production line version."""
    job = _require_job(job_id)

    if not db.count_work_units(job_id):
        raise Blocked("This job has no work units. Import a CSV before starting it.")

    version_id = job_version_id(job)
    if version_id is None:
        raise Blocked("This job's production line has no version to run.")
    if not _each(_operation, db.get_operations(version_id)):
        raise Blocked("This job's production line has no operations."
                      " An operator would have nothing to do.")

    # Pinned only on the first start. A job that stops and starts again keeps
    # the version its finished units were made under.
    if job.versionId is None:
        db.pin_job_version(job_id, version_id)

    db.freeze_version(version_id)
    db.set_job_active(job_id, True)

    # Clear only the pauses this job's own stop raised. An operator who chose
    # to take a break is still on break.
    resumed = db.resume_admin_paused_lines(job_id)
    db.close_admin_pause_events(job_id)

    return StartedJob(jobId=job_id, versionId=version_id, operatorsResumed=resumed)


def stop_job(user, job_id) -> StoppedJob:
    """Deactivate a job and pause every live line on it, origin `admin`."""
    _require_job(job_id)
    db.set_job_active(job_id, False)

    # Only lines that are working. A line already paused or stopped carries the
    # origin of whoever blocked it, and overwriting that would let this stop
    # clear their block when the job starts again.
    lines = _each(_line, db.get_working_lines(job_id))
    for line in lines:
        db.set_line_paused(line.id, "admin")
        db.insert_line_event(line.id, "pause", "admin", None, _user_id(user))

    return StoppedJob(jobId=job_id, operatorsPaused=len(lines))


def save_job(user, job_id, name, production_line_id, scheduled_start,
             scheduled_completion) -> SavedJob:
    """Create or update a job. `job_id` of `None` creates.

    Raises `ValidationError` when the completion date precedes the start.
    """
    name = (name or "").strip()
    if not name:
        raise ValidationError("A job needs a name.")
    if not scheduled_start or not scheduled_completion:
        raise ValidationError("A job needs a scheduled start and completion date.")
    # Both are YYYY-MM-DD, which compares correctly as text.
    if scheduled_completion < scheduled_start:
        raise ValidationError("The completion date cannot come before the start date.")

    if job_id is None:
        job_id = db.insert_job(name, production_line_id, scheduled_start,
                               scheduled_completion, _user_id(user))
        return SavedJob(jobId=job_id, created=True)

    job = _require_job(job_id)
    # The production line cannot move once the job has pinned a version: its
    # work units were imported against that line's declared columns.
    if job.versionId is not None and production_line_id != job.productionLineId:
        raise Blocked("This job has already started, so its production line cannot change.")

    db.update_job(job_id, name, production_line_id, scheduled_start, scheduled_completion)
    return SavedJob(jobId=job_id, created=False)


def delete_job(user, job_id):
    """Raises `Blocked` while active, or once a unit is complete or failed."""
    job = _require_job(job_id)
    if job.active:
        raise Blocked("Stop this job before deleting it.")

    worked = _each(_state_count, db.worked_work_unit_counts(job_id))
    if worked:
        raise Blocked("This job cannot be deleted because operators have already worked it."
                      " Deleting it would discard their record.",
                      [f"{row.count} {row.state}" for row in worked])

    db.delete_job(job_id)


def maybe_deactivate_job(job_id) -> bool:
    """Deactivate once every work unit is resolved. Called after each resolve."""
    job = _job(db.get_job(job_id))
    if job is None or not job.active:
        return False
    if db.count_unresolved_work_units(job_id):
        return False
    # A job with no work units has not finished; it has not started.
    if not db.count_work_units(job_id):
        return False

    db.set_job_active(job_id, False)
    return True


def requeue_work_unit(user, work_unit_id) -> RequeuedWorkUnit:
    """Clear a failed unit's progress and return it to the front of the queue."""
    unit = _require_work_unit(work_unit_id)
    if unit.state != "failed":
        raise Blocked("Only a failed work unit can be requeued.")

    # The progress is discarded rather than kept. The unit failed; whoever
    # picks it up starts from step one, and the record of the failure lives in
    # the edit and event logs.
    db.delete_unit_operations(work_unit_id)
    db.delete_unit_values(work_unit_id)
    db.delete_unit_resources(work_unit_id)
    db.requeue_work_unit(work_unit_id)

    job = _job(db.get_job(unit.jobId))
    reactivated = False
    if job and not job.active and job.versionId is not None:
        # The job auto-deactivated when its last unit resolved. Putting work
        # back on it makes it live again without an admin having to notice.
        db.set_job_active(job.id, True)
        reactivated = True

    return RequeuedWorkUnit(workUnitId=work_unit_id, jobId=unit.jobId,
                            jobReactivated=reactivated)


def job_throughput(job_id, window_minutes: int = 60) -> Throughput:
    """Units per hour and average cycle time over a trailing window.

    Both are `None` when no unit completed inside it.
    """
    units = _each(_completed_unit, db.get_units_completed_since(job_id, window_minutes))
    if not units:
        return Throughput(unitsInWindow=0, windowMinutes=window_minutes,
                          unitsPerHour=None, avgCycleSeconds=None)

    cycles = []
    for unit in units:
        if not unit.startedAt:
            continue
        started = _parse_time(unit.startedAt)
        completed = _parse_time(unit.completedAt)
        seconds = (completed - started).total_seconds()
        # Time the line was blocked is not time the unit took. Without this a
        # lunch break makes an operator look slow.
        seconds -= _blocked_seconds(unit.lineId, started, completed)
        cycles.append(max(seconds, 0))

    return Throughput(
        unitsInWindow=len(units),
        windowMinutes=window_minutes,
        # Scaled to the hour so a 20-minute window and a 2-hour one read on the
        # same axis.
        unitsPerHour=len(units) * 60.0 / window_minutes,
        avgCycleSeconds=(sum(cycles) / len(cycles)) if cycles else None,
    )


def _parse_time(value: str) -> datetime:
    """Parse a SQLite `datetime('now')` stamp, which is UTC to the second."""
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _blocked_seconds(line_id: Optional[int], started: datetime, completed: datetime) -> float:
    """How much of a unit's wall clock its line spent paused or stopped."""
    if line_id is None:
        return 0.0

    total = 0.0
    for event in _each(_interval, db.get_blocking_events(line_id)):
        block_start = _parse_time(event.startedAt)
        # An interval still open is blocking right now, so it runs to the
        # present rather than being ignored.
        block_end = _parse_time(event.endedAt) if event.endedAt else datetime.utcnow()
        overlap_start = max(block_start, started)
        overlap_end = min(block_end, completed)
        if overlap_end > overlap_start:
            total += (overlap_end - overlap_start).total_seconds()
    return total


# --- Lines ---------------------------------------------------------------

def join_line(user, job_id, resources) -> JoinedLine:
    """Create or resume the caller's line, checking out one resource per pool."""
    user_id = _user_id(user)
    job = _require_job(job_id)
    if not job.active:
        raise Blocked("This job is not running.")

    elsewhere = _each(_live_line, db.get_live_lines_elsewhere(user_id, job_id, LIVE_STATES))
    if elsewhere:
        raise Blocked("You are already on a line. Leave it before joining another job.",
                      [row.jobName for row in elsewhere])

    existing = _line(db.get_line_for(job_id, user_id))
    line_id = existing.id if existing else None

    required = _each(_required_pool, db.get_version_pools(job_version_id(job)))
    chosen = {int(entry["poolId"]): int(entry["resourceId"]) for entry in (resources or [])}

    missing = [pool.poolName for pool in required if pool.poolId not in chosen]
    if missing:
        raise ValidationError("Choose a resource for every pool this production line requires: "
                              + ", ".join(missing))

    # Everything is checked before anything is written, so a refused join
    # leaves no half-formed line holding half its resources.
    for pool in required:
        resource = _resource(db.get_resource_in_pool(chosen[pool.poolId], pool.poolId))
        if resource is None:
            raise ValidationError(f"That resource is not part of “{pool.poolName}”.")
        if not resource.inService:
            raise Blocked(f"“{resource.name}” is out of service.", [resource.name])
        if resource.heldByLineId is not None and resource.heldByLineId != line_id:
            raise Blocked(f"“{resource.name}” is checked out to another operator.",
                          [resource.name])

    if existing:
        # The record is permanent: rejoining reuses it, so an operator's
        # completed and failed counts carry across their whole shift.
        db.set_line_working(line_id)
        db.close_line_events(line_id)
    else:
        line_id = db.insert_line(job_id, user_id)

    for pool in required:
        resource_id = chosen[pool.poolId]
        # The checkout is conditional, so an operator who chose the same card
        # a moment later loses the race here rather than double-booking it.
        if not db.checkout_resource(resource_id, line_id):
            raise Blocked("That resource was just taken by another operator."
                          " Choose another and try again.")
        db.put_line_resource(line_id, pool.poolId, resource_id)

    db.insert_closed_line_event(line_id, "join", user_id)
    return JoinedLine(lineId=line_id, jobId=job_id, rejoined=existing is not None)


def leave_line(actor, line_id) -> LeftLine:
    """Release the work unit, return the resources, end the line.

    `actor` may be the operator or an admin acting from the dashboard.
    """
    line = _require_line(line_id)

    # A unit in hand goes back to the queue with its progress intact. The next
    # operator to pull it resumes where this one stopped, which is why a
    # partially-worked unit outranks an untouched one.
    released = db.release_work_units_of_line(line_id)

    db.release_resources_of_line(line_id)
    db.delete_line_resources(line_id)

    db.close_line_events(line_id)
    # The record itself is never deleted: it carries the operator's metrics.
    db.set_line_left(line_id)
    db.insert_closed_line_event(line_id, "leave", _user_id(actor))

    return LeftLine(lineId=line_id, jobId=line.jobId, workUnitsReleased=released)


def set_line_state(actor, line_id, state, origin, reason=None) -> LineStateChange:
    """Move a line between working, paused, and stopped.

    Only the origin that raised a block may clear it — an operator cannot
    resume a line their manager stopped.
    """
    if state not in LIVE_STATES:
        raise ValidationError(f"A line cannot be set to “{state}”.")

    line = _require_line(line_id)

    if state == "working":
        blocking = (line.stopOrigin if line.state == "stopped"
                    else line.pauseOrigin if line.state == "paused"
                    else None)
        # `window` is not a person: closing the window blocks the line, and
        # whoever comes back may clear it.
        if blocking and blocking != origin and blocking != "window":
            raise Blocked(f"This line was stopped by the {blocking},"
                          f" and only the {blocking} can resume it.")
        db.close_line_events(line_id)
        db.set_line_working(line_id)

    elif state == "paused":
        db.set_line_paused(line_id, origin)
        db.insert_line_event(line_id, "pause", origin, reason, _user_id(actor))

    else:
        db.set_line_stopped(line_id, origin, reason)
        db.insert_line_event(line_id, "stop", origin, reason, _user_id(actor))

    return LineStateChange(lineId=line_id, jobId=line.jobId, state=state, origin=origin)


# --- Work ----------------------------------------------------------------

def pull_work_unit(user, line_id) -> Optional[WorkUnitSummary]:
    """Claim the next queued unit, or `None` when nothing is available."""
    line = _require_line(line_id)
    job = _require_job(line.jobId)
    if not job.active:
        raise Blocked("This job is not running.")

    # Retrying covers the loser of a simultaneous claim, who simply takes the
    # next unit. Bounded rather than unbounded: on a busy line the queue is
    # long enough that a handful of attempts always lands, and a bound cannot
    # spin if some other rule leaves a unit in a state this never resolves.
    for _ in range(10):
        if db.claim_next_work_unit(job.id, line_id):
            unit = _work_unit(db.get_claimed_work_unit(line_id))
            if unit:
                db.touch_line(line_id)
                return _work_unit_summary(unit, _declared_columns(job))
        if not db.count_available_work_units(job.id):
            return None
    return None


def _require_held(unit, user):
    """The caller must be the operator holding this unit.

    Without this any signed-in operator could complete, fail, or edit a unit
    another operator is working, or one nobody has pulled — the queue would
    stop meaning anything, and the record of who did the work would be wrong.
    An admin is no exception: the dashboard reads a unit's log and requeues it,
    it does not work it.
    """
    if unit.lineId is None:
        raise Blocked("Pull this work unit before working it.")
    line = _line(db.get_line(unit.lineId))
    if line is None or line.userId != _user_id(user):
        raise Blocked("Another operator is working this unit.")
    return line


def _require_operation(version_id: int, step: int):
    operation = _operation(db.get_operation_at(version_id, step))
    if operation is None:
        raise ValidationError(f"This production line has no step {step}.")
    return operation


def _is_true(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _validate_values(operation, values: Dict[str, Any]):
    """Every required input on an operation must carry a value."""
    for section in _each(_section, db.get_sections(operation.id)):
        if not section.name or not section.required:
            continue
        value = (values or {}).get(section.name)
        label = section.label or section.name
        if section.sectionType == "checkbox":
            # An unticked required checkbox is the operator saying "no", which
            # is exactly what the step asked them to confirm.
            if not _is_true(value):
                raise ValidationError(f"“{label}” must be confirmed before continuing.")
        elif value is None or str(value).strip() == "":
            raise ValidationError(f"“{label}” is required.")


def _store_values(work_unit_id: int, operation, step: int, values: Dict[str, Any]):
    """Write one row per named section, so a token can address each by name."""
    for section in _each(_section, db.get_sections(operation.id)):
        name = section.name
        if not name or name not in (values or {}):
            continue
        value = values[name]
        if section.sectionType == "checkbox":
            stored = "1" if _is_true(value) else "0"
        else:
            stored = None if value is None else str(value)
        db.put_unit_value(work_unit_id, step, name, stored)


def _mark_operation(work_unit_id: int, step: int, state: str, notes, user_id):
    completed = state == "complete"
    existing = _unit_operation(db.get_unit_operation(work_unit_id, step))
    if existing:
        db.update_unit_operation(existing.id, state, notes,
                                 user_id if completed else None, completed)
    else:
        db.insert_unit_operation(work_unit_id, step, state, notes,
                                 user_id if completed else None, completed)


def _snapshot_resources(work_unit_id: int, line_id: Optional[int]):
    """Copy the resources the line held onto the finished unit.

    The values are copied rather than referenced: an admin correcting a card's
    number next month must not rewrite what this unit was built with.
    """
    if line_id is None:
        return
    for row in _each(_line_resource, db.get_line_resources(line_id)):
        db.put_unit_resource(work_unit_id, row.poolName, row.resourceName,
                             row.resourceValue)


def complete_operation(user, work_unit_id, step, values, notes) -> CompletedOperation:
    unit = _require_work_unit(work_unit_id)
    if unit.state in RESOLVED_STATES:
        raise Blocked("This work unit is finished.")
    if step != unit.currentStep:
        raise ValidationError(f"This work unit is on step {unit.currentStep}."
                              f" Steps are completed in order.")
    _require_held(unit, user)

    job = _require_job(unit.jobId)
    version_id = job_version_id(job)
    operation = _require_operation(version_id, step)

    _validate_values(operation, values)
    _store_values(work_unit_id, operation, step, values)
    _mark_operation(work_unit_id, step, "complete", notes, _user_id(user))

    unit_complete = step >= db.get_last_step(version_id)

    if unit_complete:
        db.complete_work_unit(work_unit_id, step)
        _snapshot_resources(work_unit_id, unit.lineId)
        if unit.lineId is not None:
            db.increment_units_completed(unit.lineId)
        maybe_deactivate_job(unit.jobId)
    else:
        db.set_work_unit_step(work_unit_id, step + 1)

    return CompletedOperation(workUnitId=work_unit_id, jobId=unit.jobId,
                              nextStep=None if unit_complete else step + 1,
                              unitComplete=unit_complete)


def fail_operation(user, work_unit_id, step, values, notes) -> FailedOperation:
    """Fail the unit at `step`. Notes are required."""
    if not (notes or "").strip():
        raise ValidationError("Say what went wrong. The note is the only record of the failure.")

    unit = _require_work_unit(work_unit_id)
    if unit.state in RESOLVED_STATES:
        raise Blocked("This work unit is finished.")
    _require_held(unit, user)

    job = _require_job(unit.jobId)
    operation = _require_operation(job_version_id(job), step)

    # Whatever was captured before the failure is kept, without the required
    # check: the step failed precisely because it could not be completed.
    _store_values(work_unit_id, operation, step, values)
    _mark_operation(work_unit_id, step, "pending", notes, _user_id(user))
    _snapshot_resources(work_unit_id, unit.lineId)

    db.fail_work_unit(work_unit_id, step)
    if unit.lineId is not None:
        db.increment_units_failed(unit.lineId)

    return FailedOperation(workUnitId=work_unit_id, jobId=unit.jobId, failedStep=step,
                           jobDeactivated=maybe_deactivate_job(unit.jobId))


def edit_operation(user, work_unit_id, step, values, notes) -> EditedOperation:
    """Change a completed step, resetting every later step."""
    unit = _require_work_unit(work_unit_id)
    if unit.state in RESOLVED_STATES:
        raise Blocked("This work unit is finished and can no longer be edited.")
    _require_held(unit, user)

    job = _require_job(unit.jobId)
    operation = _require_operation(job_version_id(job), step)

    _validate_values(operation, values)

    before = {row.name: row.value for row in _each(_captured, db.get_unit_values_at(work_unit_id, step))}

    # A later step may have been decided by what this one captured, so every
    # completed step after it has to be walked again. Their captured values are
    # left in place, so the operator sees what they entered last time.
    steps_reset = len(db.get_completed_steps_after(work_unit_id, step))
    db.reset_operations_after(work_unit_id, step)

    _store_values(work_unit_id, operation, step, values)
    _mark_operation(work_unit_id, step, "complete", notes, _user_id(user))

    after = {row.name: row.value for row in _each(_captured, db.get_unit_values_at(work_unit_id, step))}
    for name, new_value in after.items():
        if before.get(name) != new_value:
            db.insert_unit_edit(work_unit_id, step, name, before.get(name), new_value,
                                _user_id(user), steps_reset)

    db.set_work_unit_step(work_unit_id, step + 1)

    return EditedOperation(workUnitId=work_unit_id, jobId=unit.jobId,
                           stepsReset=steps_reset, currentStep=step + 1)


def build_context(work_unit_id, line_id) -> Dict[str, Any]:
    """Interpolation context: work unit columns, captured values, pool values."""
    unit = _require_work_unit(work_unit_id)

    operations: Dict[str, Dict[str, Any]] = {}
    for row in _each(_captured, db.get_unit_values(work_unit_id)):
        operations.setdefault(str(row.step), {})[row.name] = row.value

    pools: Dict[str, str] = {}
    if line_id is not None:
        for row in _each(_line_resource, db.get_line_resources(line_id)):
            pools[row.poolName] = row.resourceValue

    return {"workUnit": unit.input, "operations": operations, "pools": pools}


# --- Network models ------------------------------------------------------
#
# What the client receives. Rules build these from what `db.py` returns; routes
# declare them as the response type and hand them straight to FastAPI. Tests
# read them too, so a test asserts what a user can see rather than what happens
# to be in a column.

def list_pools() -> List[PoolSummary]:
    pools = []
    for pool in _each(_pool, db.get_pools()):
        resources = _each(_resource, db.get_resources(pool.id))
        pools.append(PoolSummary(
            id=pool.id,
            name=pool.name,
            resourceCount=len(resources),
            # What an operator could actually take right now.
            availableCount=len([r for r in resources
                                if r.inService and r.heldByLineId is None]),
        ))
    return pools


def get_pool_detail(pool_id) -> PoolDetail:
    pool = _pool(db.get_pool(pool_id))
    if pool is None:
        raise ValidationError("That pool no longer exists.")

    resources = []
    for row in _each(_resource, db.get_resources(pool_id)):
        holder = None
        if row.heldByLineId is not None:
            line = _line(db.get_line(row.heldByLineId))
            if line:
                holder = ResourceHolder(lineId=line.id, userId=line.userId,
                                        jobId=line.jobId)
        resources.append(Resource(id=row.id, name=row.name, value=row.value,
                                  inService=bool(row.inService), heldBy=holder))

    return PoolDetail(id=pool.id, name=pool.name, resources=resources)


def list_production_lines() -> List[ProductionLineSummary]:
    lines = []
    for line in _each(_production_line, db.get_production_lines()):
        version_id = line.currentVersionId
        lines.append(ProductionLineSummary(
            id=line.id,
            name=line.name,
            version=_version(db.get_version(version_id)).version if version_id else 0,
            operationCount=db.count_operations(version_id) if version_id else 0,
            inUse=bool(_each(_job, db.get_jobs_using_line(line.id))),
        ))
    return lines


def get_production_line_detail(line_id) -> ProductionLineDetail:
    line = _production_line(db.get_production_line(line_id))
    if line is None:
        raise ValidationError("That production line no longer exists.")

    version_id = line.currentVersionId
    version = _version(db.get_version(version_id)) if version_id else None

    return ProductionLineDetail(
        id=line.id,
        name=line.name,
        versionId=version_id,
        version=version.version if version else 0,
        frozen=bool(version.frozen) if version else False,
        inUse=bool(_each(_job, db.get_jobs_using_line(line_id))),
        columns=[NamedRef(id=row.id, name=row.name)
                 for row in _each(_column, db.get_columns(version_id))] if version_id else [],
        pools=[NamedRef(id=row.poolId, name=row.poolName)
               for row in _each(_required_pool, db.get_version_pools(version_id))] if version_id else [],
        operations=[OperationSummary(id=row.id, step=row.step, name=row.name,
                                     sectionCount=db.count_sections(row.id))
                    for row in _each(_operation, db.get_operations(version_id))] if version_id else [],
    )


def get_job_operations(job_id) -> List[OperationDetail]:
    """Every operation of the version a job runs, in step order.

    Keyed off the job rather than the production line, because a running job
    stays on the version it pinned while the line may have moved on.
    """
    version_id = job_version_id(_require_job(job_id))
    if version_id is None:
        return []
    return [get_operation_detail(operation.id)
            for operation in _each(_operation, db.get_operations(version_id))]


def get_operation_detail(operation_id) -> OperationDetail:
    operation = _operation(db.get_operation(operation_id))
    if operation is None:
        raise ValidationError("That operation no longer exists.")

    sections = [
        Section(
            id=row.id, type=row.sectionType, sortOrder=row.sortOrder,
            name=row.name, label=row.label, required=bool(row.required),
            body=row.body, imagePath=row.imagePath,
            options=[option.label for option in _each(_section_option, db.get_section_options(row.id))],
        )
        for row in _each(_section, db.get_sections(operation.id))
    ]

    return OperationDetail(id=operation.id, step=operation.step, name=operation.name,
                           versionId=operation.versionId, sections=sections)


def list_jobs() -> List[JobDetail]:
    return [get_job_detail(job.id) for job in _each(_job, db.get_jobs())]


def get_job_detail(job_id) -> JobDetail:
    job = _require_job(job_id)
    version_id = job_version_id(job)
    line = _production_line(db.get_production_line(job.productionLineId))
    version = _version(db.get_version(version_id)) if version_id else None
    return JobDetail(
        id=job.id,
        name=job.name,
        productionLineId=job.productionLineId,
        scheduledStart=job.scheduledStart,
        scheduledCompletion=job.scheduledCompletion,
        active=bool(job.active),
        # A job that has pinned a version has run. Nothing else records that,
        # and several rules turn on it.
        hasStarted=job.versionId is not None,
        versionId=job.versionId,
        workUnitCount=db.count_work_units(job_id),
        contract=JobContract(
            columns=[row.name for row in _each(_column, db.get_columns(version_id))] if version_id else [],
            pools=[row.poolName for row in _each(_required_pool, db.get_version_pools(version_id))]
                  if version_id else [],
        ),
        productionLineName=line.name if line else "",
        version=version.version if version else 0,
    )


def _work_unit_label(unit, columns: List[str]) -> str:
    """How an operator refers to a unit: its declared columns, run together."""
    values = unit.input
    return " · ".join(str(values.get(name, "")) for name in columns).strip(" ·")


def _work_unit_summary(unit, columns: List[str]) -> WorkUnitSummary:
    return WorkUnitSummary(
        id=unit.id,
        label=_work_unit_label(unit, columns),
        rowOrder=unit.rowOrder,
        input=unit.input,
        state=unit.state,
        currentStep=unit.currentStep,
        lineId=unit.lineId,
        startedAt=unit.startedAt,
        completedAt=unit.completedAt,
        failedAt=unit.failedAt,
        failedStep=unit.failedStep,
        requeuedAt=unit.requeuedAt,
    )


def _declared_columns(job) -> List[str]:
    version_id = job_version_id(job)
    return [row.name for row in _each(_column, db.get_columns(version_id))] if version_id else []


def list_work_units(job_id, state=None, names=None) -> List[WorkUnitSummary]:
    """`names` maps a user id to a full name.

    Only a route may ask BOSS who a user is, so the mapping arrives from above
    rather than being fetched here. Absent, the rows simply carry no operator.
    """
    job = _require_job(job_id)
    columns = _declared_columns(job)
    units = []
    for unit in _each(_work_unit, db.get_work_units(job_id)):
        if state and unit.state != state:
            continue
        summary = _work_unit_summary(unit, columns)
        summary.operator = (names or {}).get(_worked_by(unit), "")
        units.append(summary)
    return units


def _worked_by(unit) -> Optional[int]:
    """Who last completed a step on a unit, else whoever holds it now."""
    for operation in reversed(_each(_unit_operation, db.get_unit_operations(unit.id))):
        if operation.completedBy is not None:
            return operation.completedBy
    if unit.lineId is not None:
        line = _line(db.get_line(unit.lineId))
        return line.userId if line else None
    return None


def get_work_unit_detail(work_unit_id) -> WorkUnitDetail:
    unit = _require_work_unit(work_unit_id)
    job = _require_job(unit.jobId)
    version_id = job_version_id(job)

    captured: Dict[int, Dict[str, Any]] = {}
    for row in _each(_captured, db.get_unit_values(work_unit_id)):
        captured.setdefault(row.step, {})[row.name] = row.value

    progress = {row.step: row for row in _each(_unit_operation, db.get_unit_operations(work_unit_id))}

    operations = []
    for operation in (_each(_operation, db.get_operations(version_id)) if version_id else []):
        row = progress.get(operation.step)
        operations.append(WorkUnitOperation(
            step=operation.step,
            name=operation.name,
            # A step nobody has reached has no progress row, and reads as
            # pending rather than as missing.
            state=row.state if row else "pending",
            notes=row.notes if row else None,
            startedAt=row.startedAt if row else None,
            completedAt=row.completedAt if row else None,
            completedBy=row.completedBy if row else None,
            values=captured.get(operation.step, {}),
        ))

    return WorkUnitDetail(
        id=unit.id,
        jobId=unit.jobId,
        label=_work_unit_label(unit, _declared_columns(job)),
        state=unit.state,
        input=unit.input,
        currentStep=unit.currentStep,
        lineId=unit.lineId,
        startedAt=unit.startedAt,
        completedAt=unit.completedAt,
        failedAt=unit.failedAt,
        failedStep=unit.failedStep,
        requeuedAt=unit.requeuedAt,
        resources=_each(_used_resource, db.get_unit_resources(work_unit_id)),
        operations=operations,
        edits=[WorkUnitEdit(step=row.step, name=row.name, oldValue=row.oldValue,
                            newValue=row.newValue, editedBy=row.editedBy,
                            editedAt=row.editedAt, stepsReset=row.stepsReset)
               for row in _each(_unit_edit, db.get_unit_edits(work_unit_id))],
    )


def get_line_detail(line_id, names=None) -> LineDetail:
    line = _require_line(line_id)
    job = _require_job(line.jobId)
    version_id = job_version_id(job)
    unit = _line_work_unit(line_id)

    blocked = None
    if line.state == "stopped":
        blocked = LineBlock(kind="stopped", origin=line.stopOrigin,
                            reason=line.stopReason)
    elif line.state == "paused":
        blocked = LineBlock(kind="paused", origin=line.pauseOrigin)

    return LineDetail(
        lineId=line.id,
        jobId=line.jobId,
        userId=line.userId,
        state=line.state,
        blocked=blocked,
        pauseOrigin=line.pauseOrigin,
        stopOrigin=line.stopOrigin,
        stopReason=line.stopReason,
        unitsCompleted=line.unitsCompleted,
        unitsFailed=line.unitsFailed,
        workUnitId=unit.id if unit else None,
        fullName=(names or {}).get(line.userId, ""),
        workUnitLabel=_work_unit_label(unit, _declared_columns(job)) if unit else None,
        step=unit.currentStep if unit else None,
        stepCount=db.count_operations(version_id) if version_id else 0,
        resources=[UsedResource(pool=row.poolName, resource=row.resourceName,
                                value=row.resourceValue)
                   for row in _each(_line_resource, db.get_line_resources(line_id))],
        blockedSeconds=_blocked_seconds_total(line_id),
    )


def _blocked_seconds_total(line_id: int) -> float:
    """Every interval this line could not work, open ones running to now."""
    total = 0.0
    for event in _each(_interval, db.get_blocking_events(line_id)):
        start = _parse_time(event.startedAt)
        end = _parse_time(event.endedAt) if event.endedAt else datetime.utcnow()
        total += max((end - start).total_seconds(), 0.0)
    return total


def get_job_dashboard(job_id, window_minutes: int = 60, names=None) -> JobDashboard:
    counts = {row.state: row.count
              for row in _each(_state_count, db.count_work_units_by_state(job_id))}
    lines = [get_line_detail(row.id, names) for row in _each(_line, db.get_lines(job_id))]
    rate = job_throughput(job_id, window_minutes)

    stats = JobStats(
        total=sum(counts.values()),
        pending=counts.get("pending", 0),
        inProgress=counts.get("in_progress", 0),
        complete=counts.get("complete", 0),
        failed=counts.get("failed", 0),
        # Operators who still hold a line, however they are faring on it.
        operators=len([line for line in lines if line.state in LIVE_STATES]),
        paused=len([line for line in lines if line.state == "paused"]),
        stopped=len([line for line in lines if line.state == "stopped"]),
        unitsInWindow=rate.unitsInWindow,
        windowMinutes=rate.windowMinutes,
        unitsPerHour=rate.unitsPerHour,
        avgCycleSeconds=rate.avgCycleSeconds,
    )

    return JobDashboard(job=get_job_detail(job_id), stats=stats, lines=lines)


# --- Authoring: operations and sections ----------------------------------
#
# Every one of these edits a production line, so every one goes through
# `_editable_operation` or `editable_version` first. Editing a frozen version
# forks it, which gives every operation and section a new id — so each returns
# `forked`, and a client holding the old ids reloads when it is true.

def save_operation(user, operation_id, name) -> SavedOperation:
    """Rename an operation, forking a frozen version."""
    name = (name or "").strip()
    if not name:
        raise ValidationError("An operation needs a name.")

    operation, forked = _editable_operation(operation_id)
    db.set_operation_name(operation.id, name)
    return SavedOperation(operationId=operation.id, step=operation.step,
                          versionId=operation.versionId, forked=forked)


def delete_operation(user, operation_id) -> DeletedFromLine:
    """Remove an operation and close the gap in the step numbers."""
    operation, forked = _editable_operation(operation_id)
    version_id = operation.versionId
    db.delete_operation(operation.id)
    _renumber_steps(version_id)
    return DeletedFromLine(versionId=version_id, forked=forked)


def reorder_operations(user, line_id, operation_ids) -> SavedProductionLine:
    """Put the operations in the given order, renumbering the steps to match."""
    before = db.get_production_line(line_id)
    if before is None:
        raise ValidationError("That production line no longer exists.")

    version_id = editable_version(line_id)
    forked = version_id != before.current_version_id

    existing = {operation.step: operation
                for operation in _each(_operation, db.get_operations(version_id))}
    if forked:
        # A fork gave every operation a new id, so the ids the client sent name
        # the version it was looking at. They still name the same steps.
        old = {row.id: row.step for row in _each(_operation, db.get_operations(
            before.current_version_id))}
        wanted = [old[operation_id] for operation_id in operation_ids if operation_id in old]
    else:
        by_id = {operation.id: operation.step for operation in existing.values()}
        wanted = [by_id[operation_id] for operation_id in operation_ids if operation_id in by_id]

    if sorted(wanted) != sorted(existing):
        raise ValidationError("The new order must list every operation exactly once.")

    _apply_steps(version_id, [existing[step].id for step in wanted])
    return SavedProductionLine(lineId=line_id, versionId=version_id, forked=forked,
                               created=False)


def _renumber_steps(version_id: int):
    """Close any gap left by a delete, keeping the remaining order."""
    _apply_steps(version_id, [operation.id
                              for operation in _each(_operation, db.get_operations(version_id))])


def _apply_steps(version_id: int, operation_ids: List[int]):
    """Assign steps 1..n in the given order.

    Written in two passes through a negative range, because `(version_id, step)`
    is unique: moving step 3 to step 1 would collide with the operation still
    sitting there.
    """
    for offset, operation_id in enumerate(operation_ids, start=1):
        db.set_operation_step(operation_id, -offset)
    for offset, operation_id in enumerate(operation_ids, start=1):
        db.set_operation_step(operation_id, offset)


def _editable_section(section_id: int):
    """The section to write to, forking its version first if it is frozen.

    After a fork the caller's id names a section in history, so the copy is
    found by its position: the same operation step, the same sort order.
    """
    section = _section(db.get_section(section_id))
    if section is None:
        raise ValidationError("That section no longer exists.")

    operation, forked = _editable_operation(section.operationId)
    if not forked:
        return section, operation, False

    copies = _each(_section, db.get_sections(operation.id))
    match = [copy for copy in copies if copy.sortOrder == section.sortOrder]
    if not match:
        raise ValidationError("That section no longer exists.")
    return match[0], operation, True


def save_section(user, section_id, section_type, name=None, label=None, required=False,
                 body=None, options=None) -> SavedSection:
    """Replace a section's contents, forking a frozen version."""
    if section_type not in SECTION_TYPES:
        raise ValidationError(f"“{section_type}” is not a kind of section.")
    if section_type in INPUT_SECTION_TYPES and not (name or "").strip():
        raise ValidationError("An input section needs a name, which is how a token addresses it.")

    section, operation, forked = _editable_section(section_id)
    db.update_section(section.id, section_type, (name or "").strip() or None, label,
                      1 if required else 0, body)
    db.delete_section_options(section.id)
    for order, option in enumerate(options or []):
        db.insert_section_option(section.id, option, order)

    return SavedSection(sectionId=section.id, operationId=operation.id,
                        versionId=operation.versionId, forked=forked)


def delete_section(user, section_id) -> DeletedFromLine:
    """Remove a section and close the gap in the sort order.

    Its image file goes too. Every version owns its images outright — a fork
    copies the file — so this delete is unconditional.
    """
    section, operation, forked = _editable_section(section_id)
    _delete_image(section.imagePath)
    db.delete_section(section.id)
    _apply_sort_order(operation.id)
    return DeletedFromLine(versionId=operation.versionId, forked=forked)


def reorder_sections(user, operation_id, section_ids) -> SavedSection:
    """Put an operation's sections in the given order."""
    operation, forked = _editable_operation(operation_id)
    sections = _each(_section, db.get_sections(operation.id))

    if forked:
        original = _each(_section, db.get_sections(operation_id))
        order = {row.id: row.sortOrder for row in original}
    else:
        order = {row.id: row.sortOrder for row in sections}

    wanted = [order[section_id] for section_id in section_ids if section_id in order]
    if sorted(wanted) != sorted(row.sortOrder for row in sections):
        raise ValidationError("The new order must list every section exactly once.")

    by_sort = {row.sortOrder: row.id for row in sections}
    for position, sort_order in enumerate(wanted):
        db.set_section_sort_order(by_sort[sort_order], position)

    return SavedSection(sectionId=0, operationId=operation.id,
                        versionId=operation.versionId, forked=forked)


def _apply_sort_order(operation_id: int):
    for position, section in enumerate(_each(_section, db.get_sections(operation_id))):
        db.set_section_sort_order(section.id, position)


def _delete_image(image_path: Optional[str]):
    if not image_path:
        return
    path = os.path.join(_upload_dir(), os.path.basename(image_path))
    if os.path.isfile(path):
        os.unlink(path)


def set_section_image(user, section_id, image_path) -> SavedSection:
    """Point a section at an uploaded file, discarding the one it replaces."""
    section, operation, forked = _editable_section(section_id)
    if section.imagePath != image_path:
        _delete_image(section.imagePath)
    db.set_section_image(section.id, image_path)
    return SavedSection(sectionId=section.id, operationId=operation.id,
                        versionId=operation.versionId, forked=forked)


# --- Version history -----------------------------------------------------

def list_versions(line_id) -> List[VersionSummary]:
    """Every version of a production line, newest first."""
    return [VersionSummary(versionId=row.id, version=row.version, frozen=row.frozen,
                           createdAt=row.createdAt,
                           jobCount=db.count_jobs_using_version(row.id))
            for row in _each(_version, db.get_versions(line_id))]


def get_version_detail(version_id) -> ProductionLineDetail:
    """A version as it stands, current or historical.

    The same shape as the current line, so one controller renders both — a
    frozen one simply comes back with `frozen` true and is shown read-only.
    """
    version = _version(db.get_version(version_id))
    if version is None:
        raise ValidationError("That version no longer exists.")
    line = _production_line(db.get_production_line(version.productionLineId))

    return ProductionLineDetail(
        id=line.id,
        name=line.name,
        versionId=version.id,
        version=version.version,
        frozen=version.frozen,
        inUse=db.count_jobs_using_version(version.id) > 0,
        columns=[NamedRef(id=row.id, name=row.name)
                 for row in _each(_column, db.get_columns(version.id))],
        pools=[NamedRef(id=row.poolId, name=row.poolName)
               for row in _each(_required_pool, db.get_version_pools(version.id))],
        operations=[OperationSummary(id=row.id, step=row.step, name=row.name,
                                     sectionCount=db.count_sections(row.id))
                    for row in _each(_operation, db.get_operations(version.id))],
    )


# --- The operator's screens ----------------------------------------------

def _held_line(user_id: int) -> Optional[HeldLine]:
    """The line this operator is still on, whatever state it is in."""
    for line in _each(_line, db.get_live_lines_for(user_id, LIVE_STATES)):
        job = _job(db.get_job(line.jobId))
        return HeldLine(lineId=line.id, jobId=line.jobId, jobName=job.name if job else "")
    return None


def get_me(user, full_name: str = "") -> Me:
    user_id = _user_id(user)
    return Me(isAdmin=is_admin(user), userId=user_id,
              fullName=getattr(user, "fullName", None) or full_name,
              activeLine=_held_line(user_id))


def list_active_jobs(user) -> ActiveJobs:
    """The jobs an operator may join, and the one they are already on."""
    user_id = _user_id(user)
    jobs = []
    for job in _each(_job, db.get_active_jobs()):
        line = _production_line(db.get_production_line(job.productionLineId))
        held = _line(db.get_line_for(job.id, user_id))
        jobs.append(AvailableJob(
            jobId=job.id,
            name=job.name,
            product=line.name if line else "",
            unitsRemaining=db.count_unresolved_work_units(job.id),
            joined=held is not None and held.state in LIVE_STATES,
        ))
    return ActiveJobs(heldLine=_held_line(user_id), jobs=jobs)


def get_join_info(user, job_id) -> JoinInfo:
    """What an operator must choose to join, and anything stopping them.

    The reasons are gathered rather than raised: this screen exists to show
    them all at once, so the operator can see they need a card *and* that the
    only free one is out of service.
    """
    user_id = _user_id(user)
    job = _require_job(job_id)
    line = _production_line(db.get_production_line(job.productionLineId))

    blocked = []
    if not job.active:
        blocked.append("This job is not running.")

    elsewhere = _each(_live_line, db.get_live_lines_elsewhere(user_id, job_id, LIVE_STATES))
    if elsewhere:
        blocked.append(f"You are already on a line for {elsewhere[0].jobName}."
                       f" Leave it before joining another job.")

    if not db.count_unresolved_work_units(job_id):
        blocked.append("Every work unit on this job is finished.")

    mine = _line(db.get_line_for(job_id, user_id))
    pools = []
    for required in _each(_required_pool, db.get_version_pools(job_version_id(job))):
        free = [AvailableResource(id=row.id, name=row.name, value=row.value)
                for row in _each(_resource, db.get_resources(required.poolId))
                # A resource this operator already holds is still theirs to pick.
                if row.inService and (row.heldByLineId is None
                                      or (mine and row.heldByLineId == mine.id))]
        if not free:
            blocked.append(f"Every resource in {required.poolName} is taken or out of service.")
        pools.append(PoolChoice(poolId=required.poolId, name=required.poolName, resources=free))

    return JoinInfo(jobName=job.name, product=line.name if line else "",
                    pools=pools, blocked=blocked)


def _operator_operations(work_unit_id: Optional[int], version_id: int,
                         context: Dict[str, Any],
                         only_step: Optional[int] = None) -> List[OperatorOperation]:
    """Every step of the line, with tokens resolved and progress filled in.

    Rendering happens here rather than on the client because the same helper
    has to produce the CSV export and the work unit log.
    """
    captured: Dict[int, Dict[str, Any]] = {}
    progress: Dict[int, Any] = {}
    if work_unit_id is not None:
        for row in _each(_captured, db.get_unit_values(work_unit_id)):
            captured.setdefault(row.step, {})[row.name] = row.value
        progress = {row.step: row
                    for row in _each(_unit_operation, db.get_unit_operations(work_unit_id))}

    operations = []
    for operation in _each(_operation, db.get_operations(version_id)):
        if only_step is not None and operation.step != only_step:
            continue
        row = progress.get(operation.step)
        sections = [
            OperatorSection(
                id=section.id, type=section.sectionType, name=section.name,
                label=tokens.render(section.label, context) if section.label else section.label,
                required=section.required,
                body=tokens.render(section.body, context) if section.body else section.body,
                imagePath=section.imagePath,
                options=[option.label for option
                         in _each(_section_option, db.get_section_options(section.id))],
            )
            for section in _each(_section, db.get_sections(operation.id))
        ]
        operations.append(OperatorOperation(
            step=operation.step, name=operation.name,
            state=row.state if row else "pending",
            notes=row.notes if row else None,
            sections=sections, values=captured.get(operation.step, {})))
    return operations


def _line_work_unit(line_id: int) -> Optional[WorkUnit]:
    for unit in _each(_work_unit, db.get_work_units_for_line(line_id)):
        if unit.state == "in_progress":
            return unit
    return None


def get_line_state(line_id) -> LineState:
    """Everything the manufacturing screen draws, in one call."""
    line = _require_line(line_id)
    job = _require_job(line.jobId)
    product = _production_line(db.get_production_line(job.productionLineId))

    unit = _line_work_unit(line_id)
    context = build_context(unit.id, line_id) if unit else {}
    columns = _declared_columns(job)

    blocked = None
    if line.state == "stopped":
        blocked = LineBlock(kind="stopped", origin=line.stopOrigin, reason=line.stopReason)
    elif line.state == "paused":
        blocked = LineBlock(kind="paused", origin=line.pauseOrigin)

    return LineState(
        lineId=line.id,
        jobId=line.jobId,
        jobName=job.name,
        product=product.name if product else "",
        state=line.state,
        blocked=blocked,
        workUnit=_work_unit_summary(unit, columns) if unit else None,
        operations=_operator_operations(unit.id if unit else None,
                                        job_version_id(job), context),
        resources=[UsedResource(pool=row.poolName, resource=row.resourceName,
                                value=row.resourceValue)
                   for row in _each(_line_resource, db.get_line_resources(line_id))],
    )


def pull_work(user, line_id) -> PulledWorkUnit:
    """Claim the next unit and hand back everything needed to work it."""
    unit = pull_work_unit(user, line_id)
    resources = [UsedResource(pool=row.poolName, resource=row.resourceName,
                              value=row.resourceValue)
                 for row in _each(_line_resource, db.get_line_resources(line_id))]
    if unit is None:
        return PulledWorkUnit(empty=True, resources=resources)

    line = _require_line(line_id)
    job = _require_job(line.jobId)
    return PulledWorkUnit(
        empty=False,
        workUnit=unit,
        operations=_operator_operations(unit.id, job_version_id(job),
                                        build_context(unit.id, line_id)),
        resources=resources)


def store_section_image(section_id: int, filename: str, content: bytes) -> str:
    """Write an uploaded image and return the path the client will load it from.

    The stored name is made unique rather than reusing the uploaded one: two
    sections may both be given `front.png`, and every version owns its images
    outright so a fork can copy the file.
    """
    extension = os.path.splitext(filename or "")[1].lower() or ".png"
    if extension not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        raise ValidationError("An image must be a PNG, JPEG, GIF, or WebP file.")

    directory = _upload_dir()
    os.makedirs(directory, exist_ok=True)
    name = f"section-{section_id}-{os.urandom(4).hex()}{extension}"
    with open(os.path.join(directory, name), "wb") as handle:
        handle.write(content)
    return f"/upload/io.bithead.production/{name}"


def preview_operation(operation_id) -> List[OperatorSection]:
    """An operation rendered as an operator will read it, with stand-in values.

    The sample context is built here rather than on the client so that a
    preview and the real thing go through one renderer. Values are bracketed —
    «Location» — to make it obvious they are stand-ins, and only steps before
    this one are populated, so a forward reference stays visibly unresolved.
    """
    operation = _operation(db.get_operation(operation_id))
    if operation is None:
        raise ValidationError("That operation no longer exists.")

    version_id = operation.versionId
    context = {
        "workUnit": {row.name: f"«{row.name}»"
                     for row in _each(_column, db.get_columns(version_id))},
        "pools": {row.poolName: f"«{row.poolName}»"
                  for row in _each(_required_pool, db.get_version_pools(version_id))},
        "operations": {},
    }
    for earlier in _each(_operation, db.get_operations(version_id)):
        if earlier.step >= operation.step:
            continue
        context["operations"][str(earlier.step)] = {
            section.name: f"«{section.name}»"
            for section in _each(_section, db.get_sections(earlier.id)) if section.name}

    rendered = _operator_operations(None, version_id, context, only_step=operation.step)
    return rendered[0].sections if rendered else []


def close_stale_intervals() -> int:
    """Close pause and stop intervals left open by a restart.

    An interval with no end is treated as blocking right up to the present, so
    one left dangling would subtract the whole downtime from every cycle time
    afterwards. The line's last activity is the best evidence of when it
    actually stopped.
    """
    return db.close_intervals_at_last_active()
