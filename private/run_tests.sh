#!/bin/zsh

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

python3 -m pytest -vv --log-cli-level Info $1 $test_name
