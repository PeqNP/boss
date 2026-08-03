#
# Production — CSV import
#
# Parsing and validation are separate from persistence: `preview` reads a file
# and reports what it found without writing, so an admin confirms before any
# work unit exists.
#

import csv
import io
import json
import uuid

from typing import Any, Dict, List

from . import db
from .lib import Blocked, ValidationError

# Previews awaiting confirmation, keyed by upload id. Held in memory rather
# than in a table: an unconfirmed upload means nothing across a restart, and
# the admin is looking at the preview when they confirm it. A restart between
# the two simply asks them to choose the file again.
_PENDING: Dict[str, Dict[str, Any]] = {}


class Preview:
    """A parsed CSV awaiting confirmation."""

    def __init__(self, upload_id: str, columns: List[str], rows: List[Dict[str, str]],
                 errors: List[Dict[str, Any]]):
        self.upload_id = upload_id
        self.columns = columns
        self.rows = rows
        self.errors = errors

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_dict(self) -> Dict[str, Any]:
        # The client shows the first rows as a sample; sending thousands would
        # cost more than it tells the admin.
        return {"uploadId": self.upload_id, "columns": self.columns,
                "rowCount": self.row_count, "rows": self.rows[:50],
                "errors": self.errors}


def preview(job_id: int, file_bytes: bytes, columns: List[str]) -> Preview:
    """Parse and validate without persisting anything.

    `columns` are the ones the production line declares. A file may carry more
    — a PO number, a customer reference — and those are kept for the export
    even though no token can address them.
    """
    # `utf-8-sig` because a spreadsheet exporting CSV on Windows writes a byte
    # order mark, which would otherwise become part of the first column's name.
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))

    errors: List[Dict[str, Any]] = []
    rows: List[Dict[str, str]] = []

    try:
        header = [name.strip() for name in next(reader)]
    except StopIteration:
        header = []

    if not header:
        errors.append({"line": 1, "message": "The file is empty."})
        return Preview(_remember(job_id, [], []), [], [], errors)

    # Declared columns must be present. Reported once, against the header, so a
    # file missing a column does not also produce one error per row.
    present = {name.casefold() for name in header}
    for name in columns:
        if name.casefold() not in present:
            errors.append({"line": 1,
                           "message": f"The file has no column named “{name}”,"
                                      f" which this production line requires."})

    # Only columns actually in the header can be checked row by row.
    checkable = [name for name in columns if name.casefold() in present]

    seen: Dict[str, int] = {}
    for offset, values in enumerate(reader):
        # Line 1 is the header, so the first row of data is line 2.
        line = offset + 2
        if not any(value.strip() for value in values):
            continue

        row = {name: (values[index].strip() if index < len(values) else "")
               for index, name in enumerate(header)}

        for name in checkable:
            if not _value_of(row, name):
                errors.append({"line": line,
                               "message": f"Line {line} has no value for “{name}”."})

        fingerprint = json.dumps([row[name] for name in header])
        if fingerprint in seen:
            errors.append({"line": line,
                           "message": f"Line {line} repeats line {seen[fingerprint]}."})
        else:
            seen[fingerprint] = line

        rows.append(row)

    if not rows:
        errors.append({"line": 1, "message": "The file has a header but no work units."})

    return Preview(_remember(job_id, header, rows), header, rows, errors)


def _value_of(row: Dict[str, str], name: str) -> str:
    """A row's value for a declared column, matched the way tokens match."""
    if name in row:
        return row[name]
    folded = name.casefold()
    for key, value in row.items():
        if key.casefold() == folded:
            return value
    return ""


def _remember(job_id: int, columns: List[str], rows: List[Dict[str, str]]) -> str:
    upload_id = uuid.uuid4().hex
    _PENDING[upload_id] = {"jobId": job_id, "columns": columns, "rows": rows}
    return upload_id


def commit(job_id: int, upload_id: str) -> int:
    """Replace the job's work units with a previewed upload.

    Replacing rather than appending: the CSV is the job's work list, and an
    admin correcting a mistake uploads the corrected file, not a difference.
    """
    job = db.get_job(job_id)
    if job is None:
        raise ValidationError("That job no longer exists.")

    # `version_id` is pinned the first time a job starts, so it also records
    # that the job has run at all. Replacing the work list of a job an operator
    # has already worked would discard their progress.
    if job["active"] or job["version_id"] is not None:
        raise Blocked("Work units cannot be replaced once the job has started."
                      " Stop the job and create a new one.")

    pending = _PENDING.get(upload_id)
    if pending is None or pending["jobId"] != job_id:
        raise ValidationError("That upload is no longer available."
                              " Please choose the file again.")

    db.delete_work_units(job_id)
    for row_order, row in enumerate(pending["rows"], start=1):
        db.insert_work_unit(job_id, row_order, json.dumps(row))

    del _PENDING[upload_id]
    return len(pending["rows"])
