#
# Scheduler — what a rule raises when it will not do something.
#
# Each says what happened rather than that something went wrong, because the
# route layer turns these into a status code and the message reaches whoever
# asked. `server.py`'s `@handled` holds the mapping.
#
# Their own module so every module in `lib` can raise them without reaching
# back through the package that imports it. Singular, after the `Exception` it
# is full of.
#

class ValidationError(Exception):
    """Input that cannot be accepted, with a message meant for whoever asked."""


class Blocked(Exception):
    """Understood, and refused because of the state of something else.

    `blockers` names what is in the way, so the operator is told what to deal
    with rather than that it did not work.
    """

    def __init__(self, reason, blockers=None):
        super().__init__(reason)
        self.reason = reason
        self.blockers = blockers or []


class OTPInvalid(Exception):
    """The code given is not the code sent, and an attempt has been spent."""

    def __init__(self, message, attempts_remaining):
        super().__init__(message)
        self.attemptsRemaining = attempts_remaining


class OTPMaxAttemptsExceeded(Exception):
    """The three tries are gone. Another code has to be sent."""


class JobNotFound(Exception):
    """No appointment carries that job code."""


class NoContactChannel(Exception):
    """The customer gave nothing a code could be sent to."""


class AppointmentInactive(Exception):
    """The appointment is cancelled or finished; there is nothing to get back into."""


class CodeInvalid(Exception):
    """The code given is not the code sent."""


class CodeSpent(Exception):
    """That code has already let someone in once, which is all it is good for."""


class CodeExpired(Exception):
    """The code was right half an hour ago."""


class AppointmentLocked(Exception):
    """Too many wrong codes. The customer's door is shut, the operator's is not.

    `detail` reaches the client beside the reason. The lookup screen has a step
    for this, carrying the number to call, and it needs to tell this refusal
    from every other one without reading the sentence.
    """

    def __init__(self, message: str, business_phone: str = None):
        super().__init__(message)
        self.detail = {"locked": True, "businessPhone": business_phone}


class CallerBlocked(Exception):
    """Too many unknown job codes. This caller may not submit another for a day.

    Carries `detail` for the same reason `AppointmentLocked` does.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.detail = {"blocked": True}


class InvalidDateRange(Exception):
    """A from-date after a to-date. No range can contain anything."""


class SessionExpired(Exception):
    """The hold on a time lapsed before the customer finished with it.

    Whatever they were part-way through has to start again from choosing a
    time, because the time they had may belong to somebody else now.
    """
