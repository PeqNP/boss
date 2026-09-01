#
# Scheduler — what an appointment costs, and what has been paid against it.
#
# A payment is recorded against a job rather than replacing what it cost, so
# what was quoted and what was collected are both readable afterwards. The
# report reads the same rows back over a period.
#

from datetime import datetime
from typing import List, Optional

from .. import db
from ..model import *
from .exception import ValidationError
from .time import display_date


# Amounts are compared with a tolerance. A deposit of ten percent of a price
# ending in a third of a penny is exact in nobody's arithmetic, and a customer
# who paid what they were asked should not be a penny short of `deposit_paid`.
PENNY = 0.005


WRITTEN_OFF = "written_off"


def set_job_type_deposit(
    job_type_id: int,
    deposit_type: str,
    deposit_amount: float
) -> None:
    """Ask for a deposit on this job type. `fixed` is an amount, `percent` a rate."""
    if deposit_type not in ("fixed", "percent"):
        raise ValidationError("A deposit is either a fixed amount or a percentage.")
    db.set_job_type_deposit(job_type_id, deposit_type, deposit_amount)


def _deposit_due(cost: db.JobCostRow) -> Optional[float]:
    """What a deposit on this job comes to, or `None` if none is asked for."""
    if not cost.deposit_required or cost.deposit_amount is None:
        return None
    if cost.deposit_type == "percent":
        return (cost.cost or 0.0) * cost.deposit_amount / 100.0
    return cost.deposit_amount


def _payment_status(job_id: int) -> str:
    """Where the appointment stands, worked out from what has been taken."""
    cost = db.get_job_cost(job_id)
    if cost is None:
        return "unpaid"
    paid = db.get_paid_total(job_id)
    total = cost.cost or 0.0

    if paid + PENNY >= total and total > 0:
        return "fully_paid"
    deposit = _deposit_due(cost)
    if deposit is not None and paid + PENNY >= deposit:
        return "deposit_paid"
    return "unpaid"


def _payment_result(job_id: int) -> PaymentResult:
    cost = db.get_job_cost(job_id)
    return PaymentResult(
        jobId=job_id,
        paymentStatus=db.get_payment_status(job_id),
        paidTotal=db.get_paid_total(job_id),
        cost=(cost.cost or 0.0) if cost else 0.0
    )


def record_payment(
    job_id: int,
    amount: float,
    method: str,
    collected_by_user_id: Optional[int] = None,
    note: Optional[str] = None
) -> PaymentResult:
    """Take money against an appointment and restate where it stands.

    A payment after a write-off settles the appointment after all: the write-off
    said the business had stopped chasing it, not that it refuses to be paid.
    """
    if method not in ("stripe", "cash", "other"):
        raise ValidationError("A payment is taken by card, in cash, or some other way.")
    if amount <= 0:
        raise ValidationError("A payment has to be for something.")

    db.insert_transaction(job_id, amount, method, collected_by_user_id, note)
    db.set_payment_status(job_id, _payment_status(job_id))
    return _payment_result(job_id)


def write_off_payment(job_id: int) -> PaymentResult:
    """Stop chasing the balance. What was taken stays on the record."""
    db.set_payment_status(job_id, WRITTEN_OFF)
    return _payment_result(job_id)


def get_payments(job_id: int) -> List[Payment]:
    return [
        Payment(
            id=r.id,
            amount=r.amount,
            method=r.method,
            date=r.create_date,
            collectedBy=r.collected_by_user_id
        )
        for r in db.get_transactions(job_id)
    ]


QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}


def _period(year: int, quarter: Optional[int]) -> tuple:
    """The first and last date of a year, or of one quarter of it."""
    if quarter is None:
        return f"{year}-01-01", f"{year}-12-31"
    if quarter not in QUARTER_MONTHS:
        raise ValidationError("A quarter is 1, 2, 3 or 4.")
    first, last = QUARTER_MONTHS[quarter]
    end_day = 31 if last in (3, 12) else 30
    return f"{year}-{first:02d}-01", f"{year}-{last:02d}-{end_day:02d}"


def available_report_years(business_id: int) -> List[int]:
    """The years the report screen offers.

    Every year with an appointment in it, and this one — a business with
    nothing booked still needs a year selected for the menu to have a value.
    """
    # A list rather than a set: `get_booked_years` already answers in order,
    # and the current year is the one insertion — so the ordering is the
    # sort's doing rather than a set's iteration happening to agree.
    years = db.get_booked_years(business_id)
    current = datetime.now().year
    if current not in years:
        years.append(current)
        years.sort()
    return years


def get_financial_report(
    business_id: int,
    year: int,
    quarter: Optional[int] = None
) -> FinancialReport:
    """What a business took over a period, and what it gave up on.

    Revenue is money that arrived. A deposit is named apart from it: it is
    held against work still to come, and an owner reading one figure would be
    counting takings they may yet have to return.
    """
    from_date, to_date = _period(year, quarter)
    rows = db.get_jobs_in_period(business_id, from_date, to_date)

    revenue = sum(r.paid for r in rows)
    deposits = sum(r.paid for r in rows if r.payment_status == "deposit_paid")
    written_off = sum(max((r.cost or 0.0) - r.paid, 0.0)
                      for r in rows if r.payment_status == WRITTEN_OFF)
    return FinancialReport(
        period="quarter" if quarter is not None else "year",
        year=year,
        quarter=quarter,
        fromDate=from_date,
        toDate=to_date,
        availableYears=available_report_years(business_id),
        revenue=revenue,
        depositsCollected=deposits,
        writeOffs=written_off,
        jobsCompleted=len([r for r in rows if r.status == "completed"]),
        jobsCancelled=len([r for r in rows if r.status == "cancelled"])
    )


CSV_HEADERS = ("Job Code", "Date", "Service", "Status", "Payment Status",
               "Cost", "Paid")


def _csv_value(value) -> str:
    """One field, quoted when it would otherwise break the columns."""
    text = "" if value is None else str(value)
    if any(c in text for c in (",", '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


def export_financial_report(
    business_id: int,
    year: int,
    quarter: Optional[int] = None
) -> str:
    """The same period as a CSV, one row per appointment."""
    from_date, to_date = _period(year, quarter)
    lines = [",".join(CSV_HEADERS)]
    for r in db.get_jobs_in_period(business_id, from_date, to_date):
        lines.append(",".join(_csv_value(v) for v in (
            r.job_code, r.scheduled_date, r.job_type_name, r.status,
            r.payment_status, f"{r.cost or 0.0:.2f}", f"{r.paid:.2f}"
        )))
    return "\n".join(lines) + "\n"
