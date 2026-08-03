#
# Production — HTTP routes
#
# A thin layer. Each route authenticates, hands its body to a rule in `lib.py`,
# and returns what comes back. The domain models are already the shapes the
# client expects, so nothing is assembled here.
#
# Two things do belong here and nowhere else:
#
#   - Auth. `@require_admin()` is the BOSS super user; `@require_user()` is any
#     signed-in operator.
#   - Notifications. `send_events` needs the request to carry the caller's
#     credentials, so a route announces what its rule just did.
#

import re

from functools import wraps
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File

from lib.model import User
from lib.server import require_admin, require_user

from . import csvimport
from . import events
from . import export
from . import lib
from .db import start_database
from .lib import *
from .model import *

router = APIRouter(prefix="/api/io.bithead.production")


def start():
    """Called once by `api.py` when the service loads this app."""
    start_database()


def handled(func):
    """Turn a rule's refusal into the status the client expects.

    Rules raise rather than return, so a caller cannot ignore them, and they
    know nothing about HTTP. This is the single place that translation happens.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Blocked as blocked:
            # 409: the request was understood and refused because of the state
            # of something else, which `blockers` names.
            raise HTTPException(status_code=409,
                                detail={"reason": blocked.reason,
                                        "blockers": blocked.blockers})
        except ValidationError as invalid:
            raise HTTPException(status_code=400,
                                detail={"reason": str(invalid), "blockers": []})
    return wrapper


def _origin(user) -> str:
    """Who is blocking or clearing a line.

    Only the origin that raised a block may clear it, so this decides whether
    an operator can resume their own pause or is waiting on their manager.
    """
    return "admin" if lib.is_admin(user) else "operator"


# ---------------------------------------------------------------------------
# MARK: Who is asking
# ---------------------------------------------------------------------------

@router.get("/me", response_model=Me)
@require_user()
@handled
async def get_me(boss_user: User, request: Request):
    """The caller's role, and the line they are already on."""
    return lib.get_me(boss_user, boss_user.fullName)


# ---------------------------------------------------------------------------
# MARK: Pools
# ---------------------------------------------------------------------------

@router.get("/pools", response_model=List[PoolSummary])
@require_admin()
@handled
async def get_pools(request: Request):
    return lib.list_pools()


@router.get("/pools/picker", response_model=List[PoolSummary])
@require_admin()
@handled
async def get_pools_picker(request: Request):
    """The same list, read by the production line editor."""
    return lib.list_pools()


@router.get("/pool/{pool_id}", response_model=PoolDetail)
@require_admin()
@handled
async def get_pool(pool_id: int, request: Request):
    return lib.get_pool_detail(pool_id)


@router.post("/pool", response_model=SavedPool)
@require_admin()
@handled
async def create_pool(body: SavePoolInput, boss_user: User, request: Request):
    return lib.save_pool(boss_user, None, body.name)


@router.put("/pool/{pool_id}", response_model=SavedPool)
@require_admin()
@handled
async def update_pool(pool_id: int, body: SavePoolInput, boss_user: User, request: Request):
    return lib.save_pool(boss_user, pool_id, body.name)


@router.delete("/pool/{pool_id}", response_model=OK)
@require_admin()
@handled
async def delete_pool(pool_id: int, boss_user: User, request: Request):
    lib.delete_pool(boss_user, pool_id)
    return OK()


@router.post("/pool/{pool_id}/resource", response_model=SavedResource)
@require_admin()
@handled
async def create_resource(pool_id: int, body: SaveResourceInput, boss_user: User,
                          request: Request):
    return lib.save_resource(boss_user, pool_id, None, body.name, body.value, body.inService)


@router.put("/resource/{resource_id}", response_model=SavedResource)
@require_admin()
@handled
async def update_resource(resource_id: int, body: SaveResourceInput, boss_user: User,
                          request: Request):
    return lib.save_resource(boss_user, None, resource_id, body.name, body.value, body.inService)


@router.delete("/resource/{resource_id}", response_model=OK)
@require_admin()
@handled
async def delete_resource(resource_id: int, boss_user: User, request: Request):
    lib.delete_resource(boss_user, resource_id)
    return OK()


@router.post("/resource/{resource_id}/return", response_model=ReturnedResource)
@require_admin()
@handled
async def return_resource(resource_id: int, boss_user: User, request: Request):
    """Force a held resource back into its pool, leaving the line alone."""
    returned = lib.return_resource(boss_user, resource_id)
    if returned.lineId is not None:
        line = lib.get_line_detail(returned.lineId)
        await events.send(request, events.LINE_STATUS, {"lineId": line.lineId,
                                                        "jobId": line.jobId},
                          events.everyone(line.jobId))
    return returned


# ---------------------------------------------------------------------------
# MARK: Production lines
# ---------------------------------------------------------------------------

@router.get("/production-lines", response_model=List[ProductionLineSummary])
@require_admin()
@handled
async def get_production_lines(request: Request):
    return lib.list_production_lines()


@router.get("/production-line/{line_id}", response_model=ProductionLineDetail)
@require_admin()
@handled
async def get_production_line(line_id: int, request: Request):
    return lib.get_production_line_detail(line_id)


@router.post("/production-line", response_model=SavedProductionLine)
@require_admin()
@handled
async def create_production_line(body: SaveProductionLineInput, boss_user: User,
                                 request: Request):
    return lib.save_production_line(boss_user, None, body.name, body.columns, body.poolIds)


@router.put("/production-line/{line_id}", response_model=SavedProductionLine)
@require_admin()
@handled
async def update_production_line(line_id: int, body: SaveProductionLineInput, boss_user: User,
                                 request: Request):
    """Forks when the current version is frozen; the client reloads on `forked`."""
    return lib.save_production_line(boss_user, line_id, body.name, body.columns, body.poolIds)


@router.delete("/production-line/{line_id}", response_model=OK)
@require_admin()
@handled
async def delete_production_line(line_id: int, boss_user: User, request: Request):
    lib.delete_production_line(boss_user, line_id)
    return OK()


@router.post("/production-line/{line_id}/validate", response_model=LineValidation)
@require_admin()
@handled
async def validate_production_line(line_id: int, request: Request):
    """Every token that does not resolve, so the admin can fix them all at once."""
    detail = lib.get_production_line_detail(line_id)
    errors = lib.validate_line(detail.versionId) if detail.versionId else []
    return LineValidation(
        valid=not errors,
        errors=[TokenErrorDetail(step=error.step, operationName=error.operation_name,
                                 token=error.token, reason=error.reason)
                for error in errors])


@router.get("/production-line/{line_id}/versions", response_model=List[VersionSummary])
@require_admin()
@handled
async def get_production_line_versions(line_id: int, request: Request):
    return lib.list_versions(line_id)


@router.get("/production-line-version/{version_id}", response_model=ProductionLineDetail)
@require_admin()
@handled
async def get_production_line_version(version_id: int, request: Request):
    """A historical version, in the same shape, shown read-only when frozen."""
    return lib.get_version_detail(version_id)


@router.post("/production-line/{line_id}/operation", response_model=SavedOperation)
@require_admin()
@handled
async def create_operation(line_id: int, body: SaveOperationInput, boss_user: User,
                           request: Request):
    return lib.add_operation(boss_user, line_id, body.name)


@router.post("/production-line/{line_id}/operations/order", response_model=SavedProductionLine)
@require_admin()
@handled
async def reorder_operations(line_id: int, body: ReorderOperationsInput, boss_user: User,
                             request: Request):
    return lib.reorder_operations(boss_user, line_id, body.operationIds)


# ---------------------------------------------------------------------------
# MARK: Operations and sections
# ---------------------------------------------------------------------------

@router.get("/operation/{operation_id}", response_model=OperationDetail)
@require_admin()
@handled
async def get_operation(operation_id: int, request: Request):
    return lib.get_operation_detail(operation_id)


@router.put("/operation/{operation_id}", response_model=SavedOperation)
@require_admin()
@handled
async def update_operation(operation_id: int, body: SaveOperationInput, boss_user: User,
                           request: Request):
    return lib.save_operation(boss_user, operation_id, body.name)


@router.delete("/operation/{operation_id}", response_model=DeletedFromLine)
@require_admin()
@handled
async def delete_operation(operation_id: int, boss_user: User, request: Request):
    return lib.delete_operation(boss_user, operation_id)


@router.post("/operation/{operation_id}/sections/order", response_model=SavedSection)
@require_admin()
@handled
async def reorder_sections(operation_id: int, body: ReorderSectionsInput, boss_user: User,
                           request: Request):
    return lib.reorder_sections(boss_user, operation_id, body.sectionIds)


@router.post("/operation/{operation_id}/section", response_model=SavedSection)
@require_admin()
@handled
async def create_section(operation_id: int, body: SaveSectionInput, boss_user: User,
                         request: Request):
    return lib.add_section(boss_user, operation_id, body.type, name=body.name, label=body.label,
                           required=body.required, body=body.body, options=body.options)


@router.put("/section/{section_id}", response_model=SavedSection)
@require_admin()
@handled
async def update_section(section_id: int, body: SaveSectionInput, boss_user: User,
                         request: Request):
    return lib.save_section(boss_user, section_id, body.type, name=body.name, label=body.label,
                            required=body.required, body=body.body, options=body.options)


@router.delete("/section/{section_id}", response_model=DeletedFromLine)
@require_admin()
@handled
async def delete_section(section_id: int, boss_user: User, request: Request):
    return lib.delete_section(boss_user, section_id)


@router.post("/section/{section_id}/image", response_model=SavedSection)
@require_admin()
@handled
async def upload_section_image(section_id: int, boss_user: User, request: Request,
                               file: UploadFile = File(...)):
    """Store the file, then point the section at it.

    Every version owns its images outright — a fork copies the file — so the
    name is made unique here rather than reused.
    """
    image_path = lib.store_section_image(section_id, file.filename, await file.read())
    return lib.set_section_image(boss_user, section_id, image_path)


# ---------------------------------------------------------------------------
# MARK: Jobs
# ---------------------------------------------------------------------------

@router.get("/jobs", response_model=List[JobDetail])
@require_admin()
@handled
async def get_jobs(request: Request):
    return lib.list_jobs()


@router.get("/job/{job_id}", response_model=JobDetail)
@require_admin()
@handled
async def get_job(job_id: int, request: Request):
    return lib.get_job_detail(job_id)


@router.post("/job", response_model=SavedJob)
@require_admin()
@handled
async def create_job(body: SaveJobInput, boss_user: User, request: Request):
    return lib.save_job(boss_user, None, body.name, body.productionLineId,
                        body.scheduledStart, body.scheduledCompletion)


@router.put("/job/{job_id}", response_model=SavedJob)
@require_admin()
@handled
async def update_job(job_id: int, body: SaveJobInput, boss_user: User, request: Request):
    return lib.save_job(boss_user, job_id, body.name, body.productionLineId,
                        body.scheduledStart, body.scheduledCompletion)


@router.delete("/job/{job_id}", response_model=OK)
@require_admin()
@handled
async def delete_job(job_id: int, boss_user: User, request: Request):
    lib.delete_job(boss_user, job_id)
    return OK()


@router.post("/job/{job_id}/start", response_model=StartedJob)
@require_admin()
@handled
async def start_job(job_id: int, boss_user: User, request: Request):
    """Pin and freeze the version, and put every paused operator back to work."""
    started = lib.start_job(boss_user, job_id)
    await events.send(request, events.JOB_STATUS, {"jobId": job_id, "active": True},
                      events.everyone(job_id))
    return started


@router.post("/job/{job_id}/stop", response_model=StoppedJob)
@require_admin()
@handled
async def stop_job(job_id: int, boss_user: User, request: Request):
    # Recipients are read before the rule runs: stopping pauses the lines, and
    # the operators on them are exactly who needs to hear about it.
    recipients = events.everyone(job_id)
    stopped = lib.stop_job(boss_user, job_id)
    await events.send(request, events.JOB_STATUS, {"jobId": job_id, "active": False}, recipients)
    return stopped


@router.post("/job/{job_id}/work-units/preview", response_model=CsvPreview)
@require_admin()
@handled
async def preview_work_units(job_id: int, request: Request, file: UploadFile = File(...)):
    """Parse and report, writing nothing until the admin confirms."""
    columns = lib.get_job_detail(job_id).contract.columns
    return csvimport.preview(job_id, await file.read(), columns)


@router.post("/job/{job_id}/work-units/commit", response_model=CommittedUpload)
@require_admin()
@handled
async def commit_work_units(job_id: int, body: CommitUploadInput, request: Request):
    return CommittedUpload(workUnitCount=csvimport.commit(job_id, body.uploadId))


@router.get("/job/{job_id}/dashboard", response_model=JobDashboard)
@require_admin()
@handled
async def get_job_dashboard(job_id: int, request: Request):
    return lib.get_job_dashboard(job_id)


@router.get("/job/{job_id}/work-units", response_model=List[WorkUnitSummary])
@require_admin()
@handled
async def get_work_units(job_id: int, request: Request, state: Optional[str] = None):
    return lib.list_work_units(job_id, state)


@router.get("/work-unit/{work_unit_id}", response_model=WorkUnitDetail)
@require_admin()
@handled
async def get_work_unit(work_unit_id: int, request: Request):
    return lib.get_work_unit_detail(work_unit_id)


@router.post("/work-unit/{work_unit_id}/requeue", response_model=RequeuedWorkUnit)
@require_admin()
@handled
async def requeue_work_unit(work_unit_id: int, boss_user: User, request: Request):
    """Clear a failed unit's progress and put it at the front of the queue."""
    requeued = lib.requeue_work_unit(boss_user, work_unit_id)
    await events.send(request, events.WORK_UNIT,
                      {"jobId": requeued.jobId, "workUnitId": work_unit_id},
                      events.everyone(requeued.jobId))
    return requeued


@router.get("/job/{job_id}/export")
@require_admin()
@handled
async def export_work_units(job_id: int, request: Request):
    """Download rather than render: the admin wants this in a spreadsheet."""
    job = lib.get_job_detail(job_id)
    slug = re.sub(r"[^a-z0-9]+", "-", job.name.lower()).strip("-") or "job"
    return Response(
        content=export.work_units_csv(job_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{slug}-work-units.csv"'})


# ---------------------------------------------------------------------------
# MARK: Line control
#
# The same five routes serve the dashboard and the floor. Who is calling
# decides the origin, and only that origin may clear the block it raised.
# ---------------------------------------------------------------------------

async def _announce_line(request: Request, line_id: int):
    line = lib.get_line_detail(line_id)
    await events.send(request, events.LINE_STATUS,
                      {"lineId": line_id, "jobId": line.jobId, "state": line.state},
                      events.everyone(line.jobId))


@router.post("/line/{line_id}/pause", response_model=LineStateChange)
@require_user()
@handled
async def pause_line(line_id: int, boss_user: User, request: Request):
    changed = lib.set_line_state(boss_user, line_id, "paused", _origin(boss_user))
    await _announce_line(request, line_id)
    return changed


@router.post("/line/{line_id}/resume", response_model=LineStateChange)
@require_user()
@handled
async def resume_line(line_id: int, boss_user: User, request: Request):
    changed = lib.set_line_state(boss_user, line_id, "working", _origin(boss_user))
    await _announce_line(request, line_id)
    return changed


@router.post("/line/{line_id}/stop", response_model=LineStateChange)
@require_user()
@handled
async def stop_line(line_id: int, body: StopLineInput, boss_user: User, request: Request):
    """Raise the andon. The line stops until the origin that raised it clears it."""
    changed = lib.set_line_state(boss_user, line_id, "stopped", _origin(boss_user), body.reason)
    await _announce_line(request, line_id)
    return changed


@router.post("/line/{line_id}/resume-line", response_model=LineStateChange)
@require_user()
@handled
async def clear_andon(line_id: int, boss_user: User, request: Request):
    changed = lib.set_line_state(boss_user, line_id, "working", _origin(boss_user))
    await _announce_line(request, line_id)
    return changed


@router.post("/line/{line_id}/leave", response_model=LeftLine)
@require_user()
@handled
async def leave_line(line_id: int, boss_user: User, request: Request):
    """Release the work unit, return the resources, end the line."""
    left = lib.leave_line(boss_user, line_id)
    await events.send(request, events.LINE_STATUS,
                      {"lineId": line_id, "jobId": left.jobId, "state": "left"},
                      events.everyone(left.jobId))
    return left


# ---------------------------------------------------------------------------
# MARK: The floor
# ---------------------------------------------------------------------------

@router.get("/active-jobs", response_model=ActiveJobs)
@require_user()
@handled
async def get_active_jobs(boss_user: User, request: Request):
    return lib.list_active_jobs(boss_user)


@router.get("/job/{job_id}/join-info", response_model=JoinInfo)
@require_user()
@handled
async def get_join_info(job_id: int, boss_user: User, request: Request):
    """What to choose to join, and every reason the operator cannot."""
    return lib.get_join_info(boss_user, job_id)


@router.post("/job/{job_id}/join", response_model=JoinedLine)
@require_user()
@handled
async def join_line(job_id: int, body: JoinLineInput, boss_user: User, request: Request):
    joined = lib.join_line(boss_user, job_id,
                           [entry.model_dump() for entry in body.resources])
    await _announce_line(request, joined.lineId)
    return joined


@router.get("/line/{line_id}/state", response_model=LineState)
@require_user()
@handled
async def get_line_state(line_id: int, request: Request):
    """Everything the manufacturing screen draws, in one call."""
    return lib.get_line_state(line_id)


@router.post("/line/{line_id}/pull", response_model=PulledWorkUnit)
@require_user()
@handled
async def pull_work(line_id: int, boss_user: User, request: Request):
    pulled = lib.pull_work(boss_user, line_id)
    if not pulled.empty:
        line = lib.get_line_detail(line_id)
        await events.send(request, events.WORK_UNIT,
                          {"jobId": line.jobId, "workUnitId": pulled.workUnit.id},
                          events.admins())
    return pulled


@router.post("/work-unit/{work_unit_id}/operation/{step}/complete",
             response_model=CompletedOperation)
@require_user()
@handled
async def complete_operation(work_unit_id: int, step: int, body: OperationValuesInput,
                             boss_user: User, request: Request):
    completed = lib.complete_operation(boss_user, work_unit_id, step, body.values, body.notes)
    await events.send(request, events.OPERATION,
                      {"jobId": completed.jobId, "workUnitId": work_unit_id, "step": step,
                       "unitComplete": completed.unitComplete},
                      events.admins())
    return completed


@router.post("/work-unit/{work_unit_id}/operation/{step}/fail", response_model=FailedOperation)
@require_user()
@handled
async def fail_operation(work_unit_id: int, step: int, body: OperationValuesInput,
                         boss_user: User, request: Request):
    """Notes are required — they are the only record of what went wrong."""
    failed = lib.fail_operation(boss_user, work_unit_id, step, body.values, body.notes)
    await events.send(request, events.WORK_UNIT,
                      {"jobId": failed.jobId, "workUnitId": work_unit_id, "state": "failed"},
                      events.everyone(failed.jobId))
    return failed


@router.post("/work-unit/{work_unit_id}/operation/{step}/edit", response_model=EditedOperation)
@require_user()
@handled
async def edit_operation(work_unit_id: int, step: int, body: OperationValuesInput,
                         boss_user: User, request: Request):
    """Correct a completed step. Every later step is reset and walked again."""
    edited = lib.edit_operation(boss_user, work_unit_id, step, body.values, body.notes)
    await events.send(request, events.OPERATION,
                      {"jobId": edited.jobId, "workUnitId": work_unit_id, "step": step,
                       "stepsReset": edited.stepsReset},
                      events.admins())
    return edited
