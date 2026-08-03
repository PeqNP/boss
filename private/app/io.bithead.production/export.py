#
# Production — CSV export
#
# One row per work unit, built entirely from the app's own models. This module
# is a consumer like any screen: it asks `lib` for a job, its operations, and
# its work units, and never touches storage.
#
# The header comes from the production line rather than from the units, so a
# job nobody has worked still exports a file an admin can read, and a job whose
# units all failed still shows every column that was meant to be filled.
#

import csv
import io

from typing import Any, Dict, List

from . import lib
from .lib import *


def work_units_csv(job_id: int) -> str:
    """Every work unit on a job as CSV.

    Columns: declared input columns, undeclared columns, state, timestamps, the
    operator, the resource used from each required pool, one column per
    operation input named `<step>.<name>`, and one notes column per operation.
    """
    job = lib.get_job_detail(job_id)
    units = lib.list_work_units(job_id)
    operations = lib.get_job_operations(job_id)

    declared = job.contract.columns

    # Columns the CSV carried that the production line never declared. No token
    # can address them, but they are often why the job was scheduled — a PO
    # number, a customer reference — so the export carries them back out.
    known = {name.casefold() for name in declared}
    extra: List[str] = []
    for unit in units:
        for name in unit.input:
            if name.casefold() not in known:
                known.add(name.casefold())
                extra.append(name)

    value_columns = [(operation.step, section.name)
                     for operation in operations
                     for section in operation.sections if section.name]

    header = (declared + extra
              + ["state", "step reached", "started", "finished", "operator"]
              + [f"pool: {name}" for name in job.contract.pools]
              + [f"{step}.{name}" for step, name in value_columns]
              + [f"{operation.step}. notes" for operation in operations])

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)

    for unit in units:
        detail = lib.get_work_unit_detail(unit.id)
        captured = {(row.step, name): value
                    for row in detail.operations
                    for name, value in row.values.items()}
        notes = {row.step: (row.notes or "") for row in detail.operations}
        resources = {row.pool: row.value for row in detail.resources}

        writer.writerow(
            [unit.input.get(name, "") for name in declared]
            + [unit.input.get(name, "") for name in extra]
            + [unit.state,
               # Where the unit got to: the step it failed on, or the one it is
               # waiting at.
               unit.failedStep if unit.state == "failed" else unit.currentStep,
               unit.startedAt or "",
               unit.completedAt or unit.failedAt or "",
               _operator_of(detail)]
            + [resources.get(name, "") for name in job.contract.pools]
            + [_render(captured.get((step, name))) for step, name in value_columns]
            + [notes.get(operation.step, "") for operation in operations])

    return out.getvalue()


def _operator_of(detail) -> Any:
    """Who last worked the unit, blank if nobody has."""
    for operation in reversed(detail.operations):
        if operation.completedBy is not None:
            return operation.completedBy
    return detail.lineId or ""


def _render(value) -> str:
    return "" if value is None else str(value)
