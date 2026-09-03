#
# Scheduler — where a message actually goes.
#
# The seam the vendor layer plugs into. The app wires a sender in at startup
# and a test wires its own; until something does, sending is a no-op rather
# than an error, so a business with no SMS or email vendor configured fails at
# the vendor check rather than here.
#
# Asked for rather than read: the sender is replaced at runtime, and a module
# importing the value would hold whatever it was at import time.
#

_sender = None

# What `record_sent` kept. Development only, and never read except through
# `last_sent`.
_sent = []


def set_sender(sender) -> None:
    """Wire up delivery. `sender(channel, destination, message)`.

    `channel` is `sms` or `email`. It is what the vendor layer routes on, and
    it is decided where the destination is chosen rather than guessed from the
    shape of an address.
    """
    global _sender
    _sender = sender


def sender():
    """Whoever is delivering messages, or `None` while nobody is."""
    return _sender


def channel_for(field_type: str) -> str:
    """Which channel a kind of contact detail is reached on."""
    return "sms" if field_type == "phone" else "email"


def send(channel: str, destination: str, message: str) -> None:
    """Deliver, when there is anything to deliver with."""
    if _sender is not None:
        _sender(channel, destination, message)


def record_sent(channel: str, destination: str, message: str) -> None:
    """Keep what would have gone out, so a test can read it back.

    Wired as the sender in development only. A verification code is sent to a
    phone nobody is holding during a test, and the customer's next step is to
    type it in — so without this the step cannot be reached at all.
    """
    _sent.append((channel, destination, message))


def last_sent():
    """The last message this recorded, or `None`.

    Asked for rather than read: `_sent` is appended to at runtime, and a caller
    importing it would hold the list as it was when they imported.
    """
    return _sent[-1] if _sent else None
