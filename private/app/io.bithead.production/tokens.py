#
# Production — token parsing, validation, and rendering
#
# Mirrors the client-side helper in the app's `Application.html`. The same
# fixtures drive both test suites, so the two implementations cannot drift.
#
#   {work_unit.Location}      -> context["workUnit"][column]
#   {operation.1.serial}      -> context["operations"][step][name]
#   {pool.Test card}          -> context["pools"][poolName]
#
# Stage 4 fills these in.
#

from typing import Any, Dict, List


class TokenError:
    """A token that does not resolve, and why."""

    def __init__(self, step: int, operation_name: str, token: str, reason: str):
        self.step = step
        self.operation_name = operation_name
        self.token = token
        self.reason = reason


def parse(text: str) -> List[str]:
    """Every token in `text`, without braces."""
    raise NotImplementedError


def render(text: str, context: Dict[str, Any]) -> str:
    """Interpolate every token against `context`.

    An absent key renders the token literally; a key that exists with no value
    renders as an empty string.
    """
    raise NotImplementedError


def render_value(value: Any) -> str:
    """A captured value as an operator should read it."""
    raise NotImplementedError


def validate(text, step, columns, pools, prior_sections) -> List[TokenError]:
    """Check every token against the declarations available at `step`.

    Only backward references are legal: an operation may reference an earlier
    operation's sections, never its own or a later one.
    """
    raise NotImplementedError
