#
# Production — CSV export
#
# One row per work unit. The header is built from the production line, not from
# the units, so a job nobody has worked still exports a file an admin can read,
# and a job whose units all failed still shows every column that was meant to
# be filled.
#

import csv
import io
import json

from typing import Any, Dict, List

from . import db
from .lib import ValidationError, job_version_id


def work_units_csv(job_id: int) -> str:
    """Every work unit on a job as CSV.

    Columns: declared input columns, undeclared columns, state, timestamps, the
    operator, the resource used from each required pool, one column per
    operation input named `<step>.<name>`, and one notes column per operation.
    """
    job = db.get_job(job_id)
    if job is None:
        raise ValidationError("That job no longer exists.")

    version_id = job_version_id(job)
    units = db.get_work_units(job_id)

    declared = [row["name"] for row in db.get_columns(version_id)]

    # Columns the CSV carried that the production line never declared. No token
    # can address them, but they are often why the job was scheduled — a PO
    # number, a customer reference — so the export carries them back out.
    known = {name.casefold() for name in declared}
    extra: List[str] = []
    inputs = []
    for unit in units:
        values = json.loads(unit["input_json"])
        inputs.append(values)
        for name in values:
            if name.casefold() not in known:
                known.add(name.casefold())
                extra.append(name)

    pools = [row["pool_name"] for row in db.get_version_pools(version_id)]

    operations = db.get_operations(version_id)
    value_columns: List[tuple] = []
    for operation in operations:
        for section in db.get_sections(operation["id"]):
            if section["name"]:
                value_columns.append((operation["step"], section["name"]))

    header = (declared + extra
              + ["state", "step reached", "started", "finished", "operator"]
              + [f"pool: {name}" for name in pools]
              + [f"{step}.{name}" for step, name in value_columns]
              + [f"{operation['step']}. notes" for operation in operations])

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)

    for unit, values in zip(units, inputs):
        captured = _values_of(unit["id"])
        notes = _notes_of(unit["id"])
        resources = _resources_of(unit["id"])
        writer.writerow(
            [values.get(name, "") for name in declared]
            + [values.get(name, "") for name in extra]
            + [unit["state"],
               unit["failed_step"] if unit["state"] == "failed" else unit["current_step"],
               unit["started_at"] or "",
               unit["completed_at"] or unit["failed_at"] or "",
               _operator_of(unit)]
            + [resources.get(name, "") for name in pools]
            + [captured.get((step, name), "") for step, name in value_columns]
            + [notes.get(operation["step"], "") for operation in operations])

    return out.getvalue()


def _operator_of(unit) -> Any:
    """Who last worked the unit, blank if nobody has.

    The last operator to complete a step, falling back to whoever holds it now
    — a unit in progress has an operator but no completed step yet.
    """
    for row in reversed(db.get_unit_operations(unit["id"])):
        if row["completed_by"] is not None:
            return row["completed_by"]
    if unit["assigned_line_id"]:
        line = db.get_line(unit["assigned_line_id"])
        if line:
            return line["user_id"]
    return ""


def _values_of(work_unit_id: int) -> Dict[tuple, str]:
    return {(row["step"], row["name"]): (row["value"] if row["value"] is not None else "")
            for row in db.get_unit_values(work_unit_id)}


def _notes_of(work_unit_id: int) -> Dict[int, str]:
    return {row["step"]: (row["notes"] or "") for row in db.get_unit_operations(work_unit_id)}


def _resources_of(work_unit_id: int) -> Dict[str, str]:
    """What the unit was built with, as recorded when it finished."""
    return {row["pool_name"]: row["resource_value"]
            for row in db.get_unit_resources(work_unit_id)}
