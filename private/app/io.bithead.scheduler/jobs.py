#
# Scheduler — work that runs on a clock rather than on a request.
#
# Two jobs, each a thin call into `lib`. The rules live there, next to
# everything else that decides anything; what is here is the schedule and the
# reporting, so a job names one thing and its log line says what happened.
#
# The service runs them — `get_jobs` is what it reads. Each runs on the event
# loop, the same place a request handler runs, because every route in this
# service already does its own database work there. These are a sweep and a
# lookup, they run at night, and neither is worth a thread.
#
# What that costs: a restart resets the timer, and nothing records when a job
# last ran. Both are fine for a sweep and a reminder, and neither would be for
# anything that has to happen exactly once.
#

import logging

from typing import List

from lib.model import AutomatedJob

from . import lib

HOURLY = 60 * 60
DAILY = 24 * 60 * 60


def hourly() -> int:
    """Sweep the holds nobody finished. Returns how many went."""
    swept = lib.cleanup_expired_sessions()
    logging.info(f"Swept {swept} expired session(s)")
    return swept


def daily() -> int:
    """Make the appointments recurrences are due, then remind tomorrow's.

    In that order: an appointment materialised today may be tomorrow's, and a
    customer who is not told about it is the one case this exists to prevent.
    """
    made = lib.materialize_recurrences()
    logging.info(f"Materialised {made} recurring appointment(s)")
    told = lib.send_reminders()
    logging.info(f"Reminded {told} customer(s)")
    years = lib.ensure_holidays()
    if years:
        logging.info(f"Filled holidays for {years} year(s)")
    return made + told


def get_jobs() -> List[AutomatedJob]:
    """What the service runs, and how often."""
    return [
        AutomatedJob(name="hourly", run=hourly, seconds=HOURLY),
        AutomatedJob(name="daily", run=daily, seconds=DAILY)
    ]
