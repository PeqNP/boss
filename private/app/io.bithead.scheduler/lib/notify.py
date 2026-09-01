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


def set_otp_sender(sender) -> None:
    """Wire up delivery. `sender(destination, code)`."""
    global _sender
    _sender = sender


def otp_sender():
    """Whoever is delivering messages, or `None` while nobody is."""
    return _sender
