#!/bin/zsh

# Only one test run at a time.
#
# Every suite writes the database its own test file names — `test-scheduler`,
# `test-production`, `test.sqlite3` — so two runs at once create and drop the
# same tables under each other. It surfaces as `no such table` and `readonly
# database` across most of the run, which reads as a broken suite rather than
# as two of them.
#
# `bin/mutate` runs the suite once per mutation and holds this lock across the
# whole set, so a run started beside it is refused rather than corrupted.
#
# `mkdir` is the atomic part: it succeeds for exactly one caller. The pid goes
# inside so a lock left by a killed run can be told from a live one.
LOCK="${TMPDIR:-/tmp}/boss-tests.lock"

if ! mkdir "$LOCK" 2>/dev/null; then
    holder=$(cat "$LOCK/pid" 2>/dev/null)
    if [[ -n "$holder" ]] && kill -0 "$holder" 2>/dev/null; then
        echo "Another test run is in progress (pid $holder)."
        exit 1
    fi
    # The holder is gone. Take the lock over.
    rm -rf "$LOCK"
    mkdir "$LOCK" || exit 1
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT INT TERM

test_name=$2
if [[ "$test_name" != "" ]]; then
    test_name="-k $test_name"

    if [[ "tests/$2.py" == "$1" ]]; then
        log_error "Do not name test defs the same as the file name. Otherwise, all tests will run."
        echo "Rename test 'def $2:' to something else and try again."
        echo "NOTE: This could have unexpected consequences. Especially in contexts where you are expecting files to exist on disk but are removed by other tests."
        exit 1
    fi
fi

# `$PYTHON` for a machine carrying several interpreters, only some of which
# have the service's dependencies. Bare `python3` is whichever the PATH
# resolves to, and the failure it gives — `No module named pytest` — reads as
# a missing package rather than as the wrong interpreter.
${PYTHON:-python3} -m pytest -vv --log-cli-level Info $1 $test_name
