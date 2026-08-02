#
# Production — CSV export
#
# One row per work unit. Stage 4 fills this in.
#

def work_units_csv(job_id: int) -> str:
    """Every work unit on a job as CSV.

    Columns: declared input columns, undeclared columns, state, operators,
    timestamps, the resource used from each required pool, one column per
    operation input named `<step>.<name>`, and one notes column per operation.
    """
    raise NotImplementedError
