#
# Production — Stub API
#
# Stage 1: every endpoint returns hard-coded fixture data. No database.
#
# The rules these routes will call are finished and tested — see `lib.py`.
# Stage 5 replaces each body below with a call into it.
#
# SECURITY TODO(Stage 5): none of these routes are decorated yet. Every route
# marked `# ADMIN` must get `@require_admin()` and every route marked `# USER`
# must get `@require_user()` before this app handles real data. Decorators are
# omitted during Stage 1 so the UI can be built without a super user session.
#

import re

from fastapi import APIRouter, Request, Response, UploadFile, File
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from .db import start_database

router = APIRouter(prefix="/api/io.bithead.production")


def start():
    """Called once by `api.py` when the service loads this app.

    Creates the schema if it does not exist. The routes below still return
    fixtures — Stage 5 replaces each body with a call into `lib`.
    """
    start_database()


# ---------------------------------------------------------------------------
# MARK: Shared models
# ---------------------------------------------------------------------------

class MeResponse(BaseModel):
    isAdmin: bool
    userId: int
    fullName: str
    activeLine: Optional[Dict[str, Any]] = None


class OK(BaseModel):
    ok: bool = True


# ---------------------------------------------------------------------------
# MARK: Fixtures
#
# One coherent world so every controller lines up with every other:
#   Pool "Test card" (3 cards) and "Printer" (2 printers)
#   Production line "CR-One Reader" v2 — 4 operations, needs Test card
#   Job "July CR-One Run" — active, 24 work units, 3 operators on lines
# ---------------------------------------------------------------------------

POOLS = [
    {
        "id": 1,
        "name": "Test card",
        "resources": [
            {"id": 1, "name": "Card 1", "value": "12345", "inService": True,
             "heldBy": {"lineId": 1, "userId": 4, "fullName": "Dana Reyes", "jobId": 1, "jobName": "July CR-One Run"}},
            {"id": 2, "name": "Card 2", "value": "67890", "inService": True, "heldBy": None},
            {"id": 3, "name": "Card 3", "value": "24680", "inService": False, "heldBy": None}
        ]
    },
    {
        "id": 2,
        "name": "Printer",
        "resources": [
            {"id": 4, "name": "Printer A", "value": "192.168.1.40", "inService": True, "heldBy": None},
            {"id": 5, "name": "Printer B", "value": "192.168.1.41", "inService": True, "heldBy": None}
        ]
    }
]

OPERATIONS = [
    {
        "id": 1, "step": 1, "name": "Scan reader",
        "sections": [
            {"id": 1, "type": "description", "sortOrder": 1, "name": None, "label": None, "required": False,
             "body": "Take the next reader from the bin and scan its serial number.\n\nThis reader will be paired to asset {work_unit.Asset}.",
             "imagePath": None, "options": []},
            {"id": 2, "type": "image", "sortOrder": 2, "name": None, "label": None, "required": False,
             "body": None, "imagePath": "/upload/io.bithead.production/reader-back.png", "options": []},
            {"id": 3, "type": "text", "sortOrder": 3, "name": "serial", "label": "Reader serial number",
             "required": True, "body": None, "imagePath": None, "options": []}
        ]
    },
    {
        "id": 2, "step": 2, "name": "Configure",
        "sections": [
            {"id": 4, "type": "description", "sortOrder": 1, "name": None, "label": None, "required": False,
             "body": "Assign reader {operation.1.serial} to Location {work_unit.Location} (Group {work_unit.Group}).",
             "imagePath": None, "options": []},
            {"id": 5, "type": "options", "sortOrder": 2, "name": "result", "label": "Configuration result",
             "required": True, "body": None, "imagePath": None, "options": ["Pass", "Retry", "Fail"]}
        ]
    },
    {
        "id": 3, "step": 3, "name": "Verify test card",
        "sections": [
            {"id": 6, "type": "description", "sortOrder": 1, "name": None, "label": None, "required": False,
             "body": "Tap the test card on reader {operation.1.serial}.\n\nValidate that you see card value: {pool.Test card}",
             "imagePath": None, "options": []},
            {"id": 7, "type": "checkbox", "sortOrder": 2, "name": "led_ok", "label": "LED is green",
             "required": True, "body": None, "imagePath": None, "options": []}
        ]
    },
    {
        "id": 4, "step": 4, "name": "Package",
        "sections": [
            {"id": 8, "type": "description", "sortOrder": 1, "name": None, "label": None, "required": False,
             "body": "Box the reader with its mount and label the box for {work_unit.Location}.",
             "imagePath": None, "options": []},
            {"id": 9, "type": "number", "sortOrder": 2, "name": "box_count", "label": "Items in box",
             "required": False, "body": None, "imagePath": None, "options": []}
        ]
    }
]

PRODUCTION_LINE = {
    "id": 1,
    "name": "CR-One Reader",
    "versionId": 2,
    "version": 2,
    "frozen": False,
    "inUse": True,
    "columns": [{"id": 1, "name": "Location"}, {"id": 2, "name": "Group"}, {"id": 3, "name": "Asset"}],
    "pools": [{"id": 1, "name": "Test card"}],
    "operations": [{"id": o["id"], "step": o["step"], "name": o["name"], "sectionCount": len(o["sections"])}
                   for o in OPERATIONS]
}

WORK_UNIT_INPUT = {"Location": "Bay 4", "Group": "Group A", "Asset": "AST-9910", "PO Number": "PO-2231"}

LINES = [
    {"lineId": 1, "userId": 4, "fullName": "Dana Reyes", "state": "working",
     "pauseOrigin": None, "stopOrigin": None, "stopReason": None,
     "workUnitLabel": "Bay 4 · Group A · AST-9910", "step": 3, "stepCount": 4,
     "resources": [{"pool": "Test card", "resource": "Card 1", "value": "12345"}], "unitsCompleted": 7},
    {"lineId": 2, "userId": 5, "fullName": "Sam Okafor", "state": "stopped",
     "pauseOrigin": None, "stopOrigin": "operator", "stopReason": "Reader will not power on",
     "workUnitLabel": "Bay 7 · Group B · AST-9931", "step": 1, "stepCount": 4,
     "resources": [{"pool": "Test card", "resource": "Card 4", "value": "13579"}], "unitsCompleted": 3},
    {"lineId": 3, "userId": 6, "fullName": "Priya Nandi", "state": "paused",
     "pauseOrigin": "window", "stopOrigin": None, "stopReason": None,
     "workUnitLabel": "Bay 2 · Group A · AST-9902", "step": 2, "stepCount": 4,
     "resources": [{"pool": "Test card", "resource": "Card 5", "value": "11223"}], "unitsCompleted": 5},
    {"lineId": 4, "userId": 7, "fullName": "Alex Kim", "state": "left",
     "pauseOrigin": None, "stopOrigin": None, "stopReason": None,
     "workUnitLabel": None, "step": None, "stepCount": 4,
     "resources": [], "unitsCompleted": 12}
]

JOBS = [
    {"id": 1, "name": "July CR-One Run", "productionLineId": 1, "productionLineName": "CR-One Reader",
     "scheduledStart": "2026-07-06", "scheduledCompletion": "2026-08-14",
     "active": True, "hasStarted": True, "workUnitCount": 24},
    {"id": 2, "name": "Pilot batch — Bay 9", "productionLineId": 1, "productionLineName": "CR-One Reader",
     "scheduledStart": "2026-08-03", "scheduledCompletion": "2026-08-07",
     "active": False, "hasStarted": False, "workUnitCount": 6},
    {"id": 3, "name": "Q4 pre-build", "productionLineId": 1, "productionLineName": "CR-One Reader",
     "scheduledStart": "2026-09-01", "scheduledCompletion": "2026-10-30",
     "active": False, "hasStarted": False, "workUnitCount": 0}
]


def _context():
    """Interpolation context matching the client-side helper's shape."""
    return {
        "workUnit": WORK_UNIT_INPUT,
        "pools": {"Test card": "12345"},
        "operations": {"1": {"serial": "CR1-00042"}, "2": {"result": "Pass"}}
    }


def _operations_for_operator(current_step):
    """Operations with per-unit state, as the Manufacturing Line renders them."""
    ops = []
    for o in OPERATIONS:
        state = "complete" if o["step"] < current_step else "pending"
        values = {}
        if o["step"] == 1 and state == "complete":
            values = {"serial": "CR1-00042"}
        elif o["step"] == 2 and state == "complete":
            values = {"result": "Pass"}
        ops.append({
            "step": o["step"], "name": o["name"], "state": state,
            "notes": "" if state == "pending" else "Scanned on second attempt.",
            "sections": o["sections"], "values": values
        })
    return ops


# ---------------------------------------------------------------------------
# MARK: Role
# ---------------------------------------------------------------------------

@router.get("/me", response_model=MeResponse)
async def get_me(request: Request):
    # TODO: resolve from BOSS session. Stub returns an admin so both surfaces
    # are reachable during Stage 1.
    return MeResponse(isAdmin=True, userId=1, fullName="Admin", activeLine=None)


# ---------------------------------------------------------------------------
# MARK: Pools — ADMIN
# ---------------------------------------------------------------------------

@router.get("/pools")
async def get_pools(request: Request):
    # TODO: GET /pools
    return {"pools": [
        {"id": p["id"], "name": p["name"],
         "resourceCount": len(p["resources"]),
         "availableCount": len([r for r in p["resources"] if r["inService"] and r["heldBy"] is None])}
        for p in POOLS
    ]}


@router.get("/pools/picker")
async def get_pools_picker(request: Request):
    # TODO: GET /pools/picker
    return {"pools": [{"id": p["id"], "name": p["name"], "resourceCount": len(p["resources"])} for p in POOLS]}


@router.get("/pool/{pool_id}")
async def get_pool(pool_id: int, request: Request):
    # TODO: GET /pool/{poolId}
    for p in POOLS:
        if p["id"] == pool_id:
            return p
    return POOLS[0]


@router.post("/pool")
async def create_pool(request: Request, body: Dict[str, Any]):
    # TODO: POST /pool
    return {"id": 99, "name": body.get("name", "New pool"), "resources": []}


@router.put("/pool/{pool_id}")
async def update_pool(pool_id: int, request: Request, body: Dict[str, Any]):
    # TODO: PUT /pool/{poolId} — 409 when renaming a pool any line version requires
    return {"id": pool_id, "name": body.get("name", ""), "resources": POOLS[0]["resources"]}


@router.delete("/pool/{pool_id}")
async def delete_pool(pool_id: int, request: Request):
    # TODO: DELETE /pool/{poolId} — 409 when referenced or held
    return {"ok": True}


@router.post("/pool/{pool_id}/resource")
async def create_resource(pool_id: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /pool/{poolId}/resource
    return {"id": 99, "name": body.get("name", ""), "value": body.get("value", ""),
            "inService": body.get("inService", True), "heldBy": None}


@router.put("/resource/{resource_id}")
async def update_resource(resource_id: int, request: Request, body: Dict[str, Any]):
    # TODO: PUT /resource/{resourceId}
    return {"id": resource_id, "name": body.get("name", ""), "value": body.get("value", ""),
            "inService": body.get("inService", True), "heldBy": None}


@router.delete("/resource/{resource_id}")
async def delete_resource(resource_id: int, request: Request):
    # TODO: DELETE /resource/{resourceId} — 409 while held
    return {"ok": True}


@router.post("/resource/{resource_id}/return")
async def return_resource(resource_id: int, request: Request):
    # TODO: POST /resource/{resourceId}/return
    return {"ok": True}


# ---------------------------------------------------------------------------
# MARK: Production lines — ADMIN
# ---------------------------------------------------------------------------

@router.get("/production-lines")
async def get_production_lines(request: Request):
    # TODO: GET /production-lines
    return {"productionLines": [
        {"id": 1, "name": "CR-One Reader", "version": 2, "operationCount": 4, "inUse": True},
        {"id": 2, "name": "CR-One Mount Kit", "version": 1, "operationCount": 2, "inUse": False}
    ]}


@router.get("/production-line/{line_id}")
async def get_production_line(line_id: int, request: Request):
    # TODO: GET /production-line/{id}
    return PRODUCTION_LINE


@router.post("/production-line")
async def create_production_line(request: Request, body: Dict[str, Any]):
    # TODO: POST /production-line
    return dict(PRODUCTION_LINE, id=99, name=body.get("name", ""), version=1, versionId=99,
                frozen=False, inUse=False, operations=[])


@router.put("/production-line/{line_id}")
async def update_production_line(line_id: int, request: Request, body: Dict[str, Any]):
    # TODO: PUT /production-line/{id} — forks when the current version is frozen
    return dict(PRODUCTION_LINE, id=line_id, name=body.get("name", ""), forked=False)


@router.delete("/production-line/{line_id}")
async def delete_production_line(line_id: int, request: Request):
    # TODO: DELETE /production-line/{id} — 409 while referenced by a job
    return {"ok": True}


@router.post("/production-line/{line_id}/validate")
async def validate_production_line(line_id: int, request: Request):
    # TODO: POST /production-line/{id}/validate
    return {"valid": True, "errors": []}


@router.get("/production-line/{line_id}/versions")
async def get_production_line_versions(line_id: int, request: Request):
    # TODO: GET /production-line/{id}/versions
    return {"versions": [
        {"versionId": 2, "version": 2, "frozen": False, "createdAt": "2026-07-20T14:02:00Z", "jobCount": 0},
        {"versionId": 1, "version": 1, "frozen": True, "createdAt": "2026-06-02T09:15:00Z", "jobCount": 3}
    ]}


@router.get("/production-line-version/{version_id}")
async def get_production_line_version(version_id: int, request: Request):
    # TODO: GET /production-line-version/{versionId}
    return dict(PRODUCTION_LINE, versionId=version_id, version=1, frozen=True)


@router.post("/production-line/{line_id}/operation")
async def create_operation(line_id: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /production-line/{id}/operation
    return {"id": 99, "step": len(OPERATIONS) + 1, "name": body.get("name", ""),
            "versionId": 2, "forked": False}


@router.post("/production-line/{line_id}/operations/order")
async def reorder_operations(line_id: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /production-line/{id}/operations/order
    ids = body.get("operationIds", [])
    ops = []
    for index, op_id in enumerate(ids):
        match = next((o for o in OPERATIONS if o["id"] == op_id), None)
        name = match["name"] if match else "Operation"
        ops.append({"id": op_id, "step": index + 1, "name": name,
                    "sectionCount": len(match["sections"]) if match else 0})
    return {"operations": ops, "versionId": 2, "forked": False}


@router.get("/operation/{operation_id}")
async def get_operation(operation_id: int, request: Request):
    # TODO: GET /operation/{operationId}
    for o in OPERATIONS:
        if o["id"] == operation_id:
            return dict(o, versionId=2)
    return dict(OPERATIONS[0], versionId=2)


@router.put("/operation/{operation_id}")
async def update_operation(operation_id: int, request: Request, body: Dict[str, Any]):
    # TODO: PUT /operation/{operationId}
    return {"id": operation_id, "step": 1, "name": body.get("name", ""),
            "versionId": 2, "forked": False, "sections": OPERATIONS[0]["sections"]}


@router.delete("/operation/{operation_id}")
async def delete_operation(operation_id: int, request: Request):
    # TODO: DELETE /operation/{operationId}
    return {"ok": True, "versionId": 2, "forked": False}


@router.post("/operation/{operation_id}/sections/order")
async def reorder_sections(operation_id: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /operation/{operationId}/sections/order
    ids = body.get("sectionIds", [])
    all_sections = [s for o in OPERATIONS for s in o["sections"]]
    sections = []
    for index, section_id in enumerate(ids):
        match = next((s for s in all_sections if s["id"] == section_id), None)
        if match is not None:
            sections.append(dict(match, sortOrder=index + 1))
    return {"sections": sections, "versionId": 2, "forked": False}


@router.post("/operation/{operation_id}/section")
async def create_section(operation_id: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /operation/{operationId}/section
    return {"id": 99, "type": body.get("type", "description"), "sortOrder": 99,
            "name": body.get("name"), "label": body.get("label"),
            "required": body.get("required", False), "body": body.get("body"),
            "imagePath": None, "options": body.get("options", []),
            "versionId": 2, "forked": False}


@router.put("/section/{section_id}")
async def update_section(section_id: int, request: Request, body: Dict[str, Any]):
    # TODO: PUT /section/{sectionId}
    return {"id": section_id, "type": body.get("type", "description"), "sortOrder": 1,
            "name": body.get("name"), "label": body.get("label"),
            "required": body.get("required", False), "body": body.get("body"),
            "imagePath": None, "options": body.get("options", []),
            "versionId": 2, "forked": False}


@router.delete("/section/{section_id}")
async def delete_section(section_id: int, request: Request):
    # TODO: DELETE /section/{sectionId}
    return {"ok": True, "versionId": 2, "forked": False}


@router.post("/section/{section_id}/image")
async def upload_section_image(section_id: int, request: Request, file: UploadFile = File(...)):
    # TODO: POST /section/{sectionId}/image — writes to /public/upload/io.bithead.production/
    return {"imagePath": "/upload/io.bithead.production/reader-back.png"}


# ---------------------------------------------------------------------------
# MARK: Jobs — ADMIN
# ---------------------------------------------------------------------------

@router.get("/jobs")
async def get_jobs(request: Request):
    # TODO: GET /jobs
    return {"jobs": JOBS}


@router.get("/job/{job_id}")
async def get_job(job_id: int, request: Request):
    # TODO: GET /job/{jobId}
    job = next((j for j in JOBS if j["id"] == job_id), JOBS[0])
    return dict(job, contract={"columns": ["Location", "Group", "Asset"], "pools": ["Test card"]})


@router.post("/job")
async def create_job(request: Request, body: Dict[str, Any]):
    # TODO: POST /job
    return dict(JOBS[2], id=99, name=body.get("name", ""),
                productionLineId=body.get("productionLineId"),
                scheduledStart=body.get("scheduledStart"),
                scheduledCompletion=body.get("scheduledCompletion"))


@router.put("/job/{job_id}")
async def update_job(job_id: int, request: Request, body: Dict[str, Any]):
    # TODO: PUT /job/{jobId}
    return dict(JOBS[1], id=job_id, name=body.get("name", ""),
                productionLineId=body.get("productionLineId"),
                scheduledStart=body.get("scheduledStart"),
                scheduledCompletion=body.get("scheduledCompletion"))


@router.delete("/job/{job_id}")
async def delete_job(job_id: int, request: Request):
    # TODO: DELETE /job/{jobId} — 409 when active or holding resolved units
    return {"ok": True}


@router.post("/job/{job_id}/work-units/preview")
async def preview_work_units(job_id: int, request: Request, file: UploadFile = File(...)):
    # TODO: POST /job/{jobId}/work-units/preview — parse + validate, do not persist
    return {
        "uploadId": "upl_stub_1",
        "columns": ["Location", "Group", "Asset", "PO Number"],
        "rowCount": 24,
        "rows": [
            {"Location": "Bay 1", "Group": "Group A", "Asset": "AST-9901", "PO Number": "PO-2201"},
            {"Location": "Bay 2", "Group": "Group A", "Asset": "AST-9902", "PO Number": "PO-2202"},
            {"Location": "Bay 4", "Group": "Group A", "Asset": "AST-9910", "PO Number": "PO-2231"},
            {"Location": "Bay 7", "Group": "Group B", "Asset": "AST-9931", "PO Number": "PO-2244"}
        ],
        "errors": []
    }


@router.post("/job/{job_id}/work-units/commit")
async def commit_work_units(job_id: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /job/{jobId}/work-units/commit
    return {"workUnitCount": 24}


@router.post("/job/{job_id}/start")
async def start_job(job_id: int, request: Request):
    # TODO: POST /job/{jobId}/start — pins + freezes the version
    return {"ok": True, "versionId": 2, "version": 2}


@router.post("/job/{job_id}/stop")
async def stop_job(job_id: int, request: Request):
    # TODO: POST /job/{jobId}/stop — pauses every live line, origin admin
    return {"ok": True, "operatorsPaused": 3}


@router.get("/job/{job_id}/dashboard")
async def get_job_dashboard(job_id: int, request: Request):
    # TODO: GET /job/{jobId}/dashboard
    job = next((j for j in JOBS if j["id"] == job_id), JOBS[0])
    return {
        "job": dict(job, version=2),
        "stats": {
            "total": 24, "pending": 9, "inProgress": 3, "complete": 11, "failed": 1,
            "operators": 3, "stopped": 1, "paused": 1,
            "windowMinutes": 60, "unitsInWindow": 6,
            "unitsPerHour": 6.0, "avgCycleSeconds": 512
        },
        "lines": LINES
    }


@router.get("/job/{job_id}/work-units")
async def get_job_work_units(job_id: int, request: Request, state: Optional[str] = None):
    # TODO: GET /job/{jobId}/work-units?state=
    units = [
        {"id": 1, "label": "Bay 1 · Group A · AST-9901", "state": "complete",
         "operator": "Dana Reyes", "startedAt": "2026-07-30T14:02:00Z", "completedAt": "2026-07-30T14:11:00Z"},
        {"id": 2, "label": "Bay 2 · Group A · AST-9902", "state": "in_progress",
         "operator": "Priya Nandi", "startedAt": "2026-07-30T15:40:00Z", "completedAt": None},
        {"id": 3, "label": "Bay 4 · Group A · AST-9910", "state": "in_progress",
         "operator": "Dana Reyes", "startedAt": "2026-07-30T15:44:00Z", "completedAt": None},
        {"id": 4, "label": "Bay 5 · Group B · AST-9920", "state": "failed",
         "operator": "Sam Okafor", "startedAt": "2026-07-30T13:05:00Z", "completedAt": None},
        {"id": 5, "label": "Bay 6 · Group B · AST-9925", "state": "pending",
         "operator": None, "startedAt": None, "completedAt": None}
    ]
    if state is not None and state != "all":
        units = [u for u in units if u["state"] == state]
    return {"workUnits": units}


@router.get("/work-unit/{work_unit_id}")
async def get_work_unit(work_unit_id: int, request: Request):
    # TODO: GET /work-unit/{workUnitId}
    return {
        "id": work_unit_id,
        "label": "Bay 4 · Group A · AST-9910",
        "state": "complete",
        "input": WORK_UNIT_INPUT,
        "resources": [{"pool": "Test card", "resource": "Card 1", "value": "12345"}],
        "operations": [
            {"step": 1, "name": "Scan reader", "state": "complete",
             "notes": "Scanned on second attempt.",
             "startedAt": "2026-07-30T14:02:00Z", "completedAt": "2026-07-30T14:04:00Z",
             "completedBy": "Dana Reyes",
             "values": [{"name": "serial", "label": "Reader serial number", "value": "CR1-00042"}]},
            {"step": 2, "name": "Configure", "state": "complete", "notes": "",
             "startedAt": "2026-07-30T14:04:00Z", "completedAt": "2026-07-30T14:07:00Z",
             "completedBy": "Dana Reyes",
             "values": [{"name": "result", "label": "Configuration result", "value": "Pass"}]},
            {"step": 3, "name": "Verify test card", "state": "complete", "notes": "",
             "startedAt": "2026-07-30T14:07:00Z", "completedAt": "2026-07-30T14:09:00Z",
             "completedBy": "Dana Reyes",
             "values": [{"name": "led_ok", "label": "LED is green", "value": "Yes"}]},
            {"step": 4, "name": "Package", "state": "complete", "notes": "",
             "startedAt": "2026-07-30T14:09:00Z", "completedAt": "2026-07-30T14:11:00Z",
             "completedBy": "Dana Reyes",
             "values": [{"name": "box_count", "label": "Items in box", "value": "2"}]}
        ],
        "edits": [
            {"step": 1, "name": "serial", "oldValue": "CR1-0042", "newValue": "CR1-00042",
             "editedBy": "Dana Reyes", "editedAt": "2026-07-30T14:06:00Z", "stepsReset": 1}
        ]
    }


@router.post("/work-unit/{work_unit_id}/requeue")
async def requeue_work_unit(work_unit_id: int, request: Request):
    # TODO: POST /work-unit/{workUnitId}/requeue
    return {"ok": True, "jobReactivated": False}


@router.get("/job/{job_id}/export")
async def export_job(job_id: int, request: Request):
    # TODO: GET /job/{jobId}/export — one row per work unit
    csv = "Location,Group,Asset,state\nBay 1,Group A,AST-9901,complete\n"

    # `Content-Disposition: attachment` is what makes the browser download the
    # file rather than render it. The filename is derived from the job so an
    # admin exporting several jobs does not end up with export(1).csv.
    job = next((j for j in JOBS if j["id"] == job_id), JOBS[0])
    slug = re.sub(r"[^a-z0-9]+", "-", job["name"].lower()).strip("-")
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{slug}-work-units.csv"'}
    )


# ---------------------------------------------------------------------------
# MARK: Line control — ADMIN origin
# ---------------------------------------------------------------------------

@router.post("/line/{line_id}/pause")
async def admin_pause_line(line_id: int, request: Request):
    # TODO: POST /line/{lineId}/pause
    return {"ok": True}


@router.post("/line/{line_id}/resume")
async def admin_resume_line(line_id: int, request: Request):
    # TODO: POST /line/{lineId}/resume
    return {"ok": True}


@router.post("/line/{line_id}/stop")
async def stop_line(line_id: int, request: Request, body: Optional[Dict[str, Any]] = None):
    # TODO: POST /line/{lineId}/stop — operator origin sends an optional reason
    return {"ok": True}


@router.post("/line/{line_id}/resume-line")
async def resume_line(line_id: int, request: Request):
    # TODO: POST /line/{lineId}/resume-line — 403 when the andon was admin-raised
    return {"ok": True}


@router.post("/line/{line_id}/leave")
async def leave_line(line_id: int, request: Request):
    # TODO: POST /line/{lineId}/leave
    return {"ok": True, "resources": [{"pool": "Test card", "resource": "Card 1", "value": "12345"}]}


# ---------------------------------------------------------------------------
# MARK: Operator — joining
# ---------------------------------------------------------------------------

@router.get("/active-jobs")
async def get_active_jobs(request: Request):
    # TODO: GET /active-jobs
    return {
        "heldLine": None,
        "jobs": [
            {"jobId": 1, "name": "July CR-One Run", "product": "CR-One Reader",
             "unitsRemaining": 12, "joined": False}
        ]
    }


@router.get("/job/{job_id}/join-info")
async def get_join_info(job_id: int, request: Request):
    # TODO: GET /job/{jobId}/join-info
    return {
        "jobName": "July CR-One Run",
        "product": "CR-One Reader",
        "pools": [
            {"poolId": 1, "name": "Test card", "resources": [
                {"id": 2, "name": "Card 2", "value": "67890"},
                {"id": 6, "name": "Card 6", "value": "33445"}
            ]}
        ],
        "blocked": []
    }


@router.post("/job/{job_id}/join")
async def join_job(job_id: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /job/{jobId}/join
    return {"lineId": 1}


# ---------------------------------------------------------------------------
# MARK: Operator — manufacturing line
# ---------------------------------------------------------------------------

@router.get("/line/{line_id}/state")
async def get_line_state(line_id: int, request: Request):
    # TODO: GET /line/{lineId}/state
    return {
        "lineId": line_id,
        "jobId": 1,
        "jobName": "July CR-One Run",
        "state": "working",
        "blocked": None,
        "workUnit": {"id": 3, "label": "Bay 4 · Group A · AST-9910",
                     "input": WORK_UNIT_INPUT, "currentStep": 3},
        "operations": _operations_for_operator(3),
        "context": _context()
    }


@router.post("/line/{line_id}/pull")
async def pull_work_unit(line_id: int, request: Request):
    # TODO: POST /line/{lineId}/pull — atomic claim of the next queued unit
    return {
        "workUnit": {"id": 3, "label": "Bay 4 · Group A · AST-9910",
                     "input": WORK_UNIT_INPUT, "currentStep": 1},
        "operations": _operations_for_operator(1),
        "context": _context()
    }


@router.post("/work-unit/{work_unit_id}/operation/{step}/complete")
async def complete_operation(work_unit_id: int, step: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /work-unit/{id}/operation/{step}/complete
    next_step = step + 1
    unit_complete = next_step > len(OPERATIONS)
    return {"nextStep": None if unit_complete else next_step, "unitComplete": unit_complete}


@router.post("/work-unit/{work_unit_id}/operation/{step}/fail")
async def fail_operation(work_unit_id: int, step: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /work-unit/{id}/operation/{step}/fail — notes are required
    return {"ok": True}


@router.post("/work-unit/{work_unit_id}/operation/{step}/edit")
async def edit_operation(work_unit_id: int, step: int, request: Request, body: Dict[str, Any]):
    # TODO: POST /work-unit/{id}/operation/{step}/edit — resets every later step
    return {"stepsReset": max(0, len(OPERATIONS) - step)}
