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
# Names are matched case-insensitively — a column or pool may be typed either
# way in a description, and whoever writes the token should not have to recall
# how the admin capitalised it.
#

import re

from typing import Any, Dict, List, Optional

# A token is any brace-delimited run containing no braces of its own. Which of
# them actually resolve is decided below, not here: `parse` reports what was
# written, so validation has something to complain about.
TOKEN = re.compile(r"\{([^{}]+)\}")

# Sentinel for "this key does not exist", which renders the token literally.
# `None` cannot serve: a section that exists and captured nothing is a
# different outcome, and renders empty.
_ABSENT = object()


class TokenError:
    """A token that does not resolve, and why."""

    def __init__(self, step: int, operation_name: str, token: str, reason: str):
        self.step = step
        self.operation_name = operation_name
        self.token = token
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {"step": self.step, "operationName": self.operation_name,
                "token": self.token, "reason": self.reason}


def _lookup(mapping: Optional[Dict[str, Any]], key: str) -> Any:
    """Case-insensitive fetch, returning `_ABSENT` when the key is not there."""
    if not isinstance(mapping, dict):
        return _ABSENT
    if key in mapping:
        return mapping[key]
    folded = key.casefold()
    for candidate, value in mapping.items():
        if str(candidate).casefold() == folded:
            return value
    return _ABSENT


def parse(text: str) -> List[str]:
    """Every token in `text`, without braces."""
    if not text:
        return []
    return TOKEN.findall(text)


def _resolve(token: str, context: Dict[str, Any]) -> Any:
    """The value a token names, or `_ABSENT` when nothing declares it."""
    namespace, _, rest = token.partition(".")
    if not rest:
        return _ABSENT

    if namespace == "work_unit":
        return _lookup(context.get("workUnit"), rest)

    if namespace == "pool":
        return _lookup(context.get("pools"), rest)

    if namespace == "operation":
        step, _, name = rest.partition(".")
        if not name:
            return _ABSENT
        sections = _lookup(context.get("operations"), step)
        if sections is _ABSENT:
            return _ABSENT
        return _lookup(sections, name)

    return _ABSENT


def render(text: str, context: Dict[str, Any]) -> str:
    """Interpolate every token against `context`.

    An absent key renders the token literally; a key that exists with no value
    renders as an empty string. Leaving an unresolvable token as written is
    deliberate — an operator who sees `{work_unit.Nope}` on the floor can
    report exactly what is wrong with the instruction. A blank cannot.
    """
    if not text:
        return ""

    def substitute(match):
        value = _resolve(match.group(1), context)
        if value is _ABSENT:
            return match.group(0)
        return render_value(value)

    return TOKEN.sub(substitute, text)


def render_value(value: Any) -> str:
    """A captured value as an operator should read it."""
    if value is None:
        return ""
    # Checked before any numeric handling, because `isinstance(True, int)` is
    # true in Python and a ticked checkbox must read as Yes, not 1.
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def validate(text, step, columns, pools, prior_sections) -> List[TokenError]:
    """Check every token against the declarations available at `step`.

    Only backward references are legal: an operation may reference an earlier
    operation's sections, never its own or a later one. `prior_sections` maps a
    step to the section names it captures.
    """
    errors = []
    known_columns = {str(c).casefold() for c in (columns or [])}
    known_pools = {str(p).casefold() for p in (pools or [])}
    by_step = {int(key): {str(n).casefold() for n in (names or [])}
               for key, names in (prior_sections or {}).items()}

    def fail(token, reason):
        errors.append(TokenError(step, None, token, reason))

    for token in parse(text):
        namespace, _, rest = token.partition(".")

        # Braces with no namespace are not addressing anything this app knows
        # about, so they are left alone rather than reported.
        if not rest:
            continue

        if namespace == "work_unit":
            if rest.casefold() not in known_columns:
                fail(token, f"The production line does not declare a column named “{rest}”.")

        elif namespace == "pool":
            if rest.casefold() not in known_pools:
                fail(token, f"The production line does not require a pool named “{rest}”.")

        elif namespace == "operation":
            referenced, _, name = rest.partition(".")
            if not name or not referenced.isdigit():
                fail(token, "An operation token reads {operation.<step>.<name>}.")
                continue
            referenced = int(referenced)
            if referenced >= step:
                fail(token, f"Step {step} can only use values captured before it,"
                            f" and step {referenced} has not run yet.")
            elif name.casefold() not in by_step.get(referenced, set()):
                fail(token, f"Step {referenced} does not capture a value named “{name}”.")

    return errors
