#!/usr/bin/env python3
#
# Tests all game related functions
#

import logging
import pytest

from datetime import datetime
from libtest import *

get_app_module("io.bithead.wordy")
from io.bithead.wordy.lib import *

logging.basicConfig(filename="unittests.log", encoding="utf-8", level=logging.INFO)

def test_game():
    set_database_name("test.sqlite3")
    delete_database()
    start_database()
    current_date = datetime.now().strftime("%m-%d-%Y")

    # describe: get next word to solve
    puzzle = get_current_puzzle(1)
    assert puzzle.date == current_date, "it: should format the date"

    daily_puzzle = get_daily_puzzle(1)
    assert puzzle == daily_puzzle, "it: the daily puzzle is the current word"

    # Scenarios
    # - User lands on page for first time
    # - User lands on page after some time, on the same day
    # - User lands on page for second time, different day

    # NOTE: As soon as a puzzle is loaded by a user, the server saves which puzzle
    # they were last on.
    next_puzzle = get_puzzle_by_date(1, current_date)
    assert puzzle == next_puzzle, "it: should be the same record"

    with pytest.raises(WordyError, match="Word must be 5 characters long"):
        guess_word("hell")

    # TODO: Clear cache
    # describe: guess word when puzzle has not yet been created
    # it: should throw exception
    # describe: guess word when puzzle has already been created
    # it: should attemp to guess

def test_friends():
    pass

def test_statistics():
    pass

def test_solver():
    pass

