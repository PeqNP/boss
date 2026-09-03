#!/usr/bin/env python3
#
# What is only true of the Scheduler.
#
# `bin/check-routes` and the other checkers are about every service, so a rule
# that names one app's concepts does not belong in them. This is where the
# Scheduler's own rules live, and `bin/check` runs it because the file is here.
#
# Usage:
#   bin/io.bithead.scheduler/check.py
#

import ast
import os
import sys

BUNDLE = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICE = os.path.join(REPO, "private", "app", BUNDLE, "__init__.py")


# Lib calls that answer without a business because what they answer is the
# platform's rather than any one business's.
PLATFORM_WIDE = {
    "get_business_templates",
    "get_schedule_timeout_minutes",
}


def handlers_dropping_the_business(text):
    """Handlers naming a business in the path that call `lib` without it.

    `_working_for` checks the caller against the business the path names. It
    says nothing about the record the path names next. A handler that then
    passes only that record's id has left the business behind, and the lib
    call has nothing to scope by — so an operator naming their own business
    and somebody else's record reaches it.

    Twenty-two functions were reached that way. A rival operator completed
    another business's appointment, which sent that business's customer a
    receipt, and read their job types in full.

    Returns (line, handler name, lib function) for each.
    """
    found = []
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        decorators = "\n".join(ast.unparse(d) for d in node.decorator_list)
        if "router." not in decorators or "{business_id}" not in decorators:
            continue
        if "business_id" not in {a.arg for a in node.args.args}:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if not (isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "lib"):
                continue
            if func.attr in PLATFORM_WIDE:
                continue
            given = {a.id for a in call.args if isinstance(a, ast.Name)}
            given |= {k.value.id for k in call.keywords
                      if isinstance(k.value, ast.Name)}
            if "business_id" not in given:
                found.append((node.lineno, node.name, func.attr))
    return found


def main():
    if not os.path.exists(SERVICE):
        print(f"  {BUNDLE} has no service to check.")
        return 0

    where = os.path.relpath(SERVICE, REPO)
    unscoped = handlers_dropping_the_business(open(SERVICE).read())
    if unscoped:
        print(f"  ERROR   {len(unscoped)} handler(s) name a business in the"
              f" path and call `lib` without it. The record they name next is"
              f" reached by its id alone, so an operator naming their own"
              f" business and somebody else's record reaches it:")
        for line, handler, fn in unscoped:
            print(f"            {where}:{line}  {handler}() -> lib.{fn}()")
        return 1

    print("  Every record a route names is reached through its business.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
