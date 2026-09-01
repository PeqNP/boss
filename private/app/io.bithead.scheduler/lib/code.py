#
# Scheduler — the codes a customer is given, and how they are shown.
#
# A job code identifies an appointment to whoever holds it; a verification code
# proves the person reading it out is the one who booked. Neither is stored as
# it was sent — a code is hashed, and a destination is masked before it is
# echoed back.
#

import hashlib
import random

from .. import db

# No `I`, `O`, `0` or `1`: a code is read out over the phone, and those are the
# pairs a person hears wrong.
JOB_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
JOB_CODE_LENGTH = 6


def _job_code() -> str:
    """A short code a customer can read out over the phone.

    The alphabet leaves out the characters that are heard or seen as each
    other — I and 1, O and 0 — because this one is spoken aloud.
    """
    import secrets
    return "".join(secrets.choice(JOB_CODE_ALPHABET) for _ in range(JOB_CODE_LENGTH))


def _hash_code(code: str, salt: str) -> str:
    import hashlib
    return hashlib.sha256((salt + code).encode()).hexdigest()


def _mask(channel: str, value: str) -> str:
    """Enough of a destination to recognise, not enough to learn.

    Someone who guessed a job code should not come away knowing the customer's
    phone number, and the customer should still know which of theirs it went
    to.
    """
    if channel == "email":
        name, _, domain = value.partition("@")
        return f"{name[:1]}{'•' * max(len(name) - 1, 1)}@{domain}"
    return f"{'•' * max(len(value) - 4, 0)}{value[-4:]}"
