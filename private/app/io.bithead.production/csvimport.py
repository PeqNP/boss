#
# Production — CSV import
#
# Parsing and validation are separate from persistence: `preview` reads a file
# and reports what it found without writing, so an admin confirms before any
# work unit exists. Stage 4 fills these in.
#

from typing import Any, Dict, List


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


def preview(job_id: int, file_bytes: bytes, columns: List[str]) -> Preview:
    """Parse and validate without persisting anything."""
    raise NotImplementedError


def commit(job_id: int, upload_id: str) -> int:
    """Replace the job's work units with a previewed upload."""
    raise NotImplementedError
