#!/usr/bin/env python3
#
# Commands that cost more than the work they do.
#
# Runs on `PreToolUse` for `Bash`. Each rule names a command that has a cheaper
# form, and blocks with the cheaper one. Exit 2 refuses the call and hands the
# reason back.
#
# Reads the hook payload on stdin.
#

import json
import re
import sys

# (matches, does not match, what to do instead)
RULES = [
    (
        re.compile(r"\bnpx playwright test\s*(?:--[\w-]+(?:[= ]\S+)?\s*)*$"),
        None,
        "That runs every UI spec, which takes five minutes and cannot be\n"
        "affected by most of what was just edited.\n\n"
        "  bin/check --ui          the specs covering what changed\n"
        "  bin/check --ui --all    every spec, at the end of a step\n\n"
        "To run one file: npx playwright test tests/<name>.spec.js"
    ),
    (
        re.compile(r"\.build/debug/boss serve"),
        re.compile(r"bin/restart"),
        "Starting Swift on its own leaves Python holding a session Swift no\n"
        "longer issues, and every route answers \"Please sign in before\n"
        "accessing this resource\".\n\n"
        "  bin/restart --swift     builds Swift, restarts it, then Python"
    ),
]


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")

    for matches, unless, instead in RULES:
        for part in re.split(r"&&|\|\||;", command):
            part = part.strip()
            if not matches.search(part):
                continue
            if unless is not None and unless.search(command):
                continue
            print(instead, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
