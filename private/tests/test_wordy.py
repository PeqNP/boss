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

logging.basicConfig(filename="unittests.log", encoding="utf-8", level=logging.WARN)

def test_game():
    set_randomize_words(False)
    set_dictionary_name("test-dictionary.csv")
    set_database_name("test.sqlite3")
    delete_database()
    start_database()
    current_date = datetime.now().strftime("%m-%d-%Y")

    word = get_word(current_date)
    assert word.word == "bigot", "it: should start with the correct word"

    # describe: get next word to solve
    puzzle = get_current_puzzle(1)
    assert puzzle.id == 1
    assert puzzle.date == current_date, "it: should format the date"
    assert puzzle.guessNumber == 0
    assert puzzle.attempts == []
    assert puzzle.keys == {}
    assert not puzzle.solved

    daily_puzzle = get_daily_puzzle(1)
    assert puzzle == daily_puzzle, "it: the daily puzzle is the current word"

    # Scenarios
    # - User lands on page for first time
    # - User lands on page after some time, on the same day
    # - User lands on page for second time, different day

    # NOTE: As soon as a puzzle is loaded by a user, the server saves which puzzle
    # they were last on.
    date_puzzle = get_puzzle_by_date(1, current_date)
    assert puzzle == date_puzzle, "it: should be the same record"

    # describe: invalid number of characters
    # it: should not change the state of the puzzle
    with pytest.raises(WordyError, match="Word must be 5 characters long"):
        guess_word(1, "hell")

    def te(letter, state):
        return TypedLetter(letter=letter, state=state)
    def s(state):
        return TypedLetterState(state)

    # describe: guess fails
    puzzle = guess_word(1, "hello")
    assert puzzle.attempts == [[te("h", "miss"), te("e", "miss"), te("l", "miss"), te("l", "miss"), te("o", "found")]]
    assert puzzle.keys == {"h": s("miss"), "e": s("miss"), "l": s("miss"), "o": s("found")}
    assert puzzle.guessNumber == 1, "it: should move to next guess number"
    assert not puzzle.solved

    # describe: guess succeeds
    puzzle = guess_word(1, "bigot")
    assert puzzle.attempts == [
        [te("h", "miss"), te("e", "miss"), te("l", "miss"), te("l", "miss"), te("o", "found")],
        [te("b", "hit"), te("i", "hit"), te("g", "hit"), te("o", "hit"), te("t", "hit")]
    ]
    assert puzzle.keys == {"h": s("miss"), "e": s("miss"), "l": s("miss"), "b": s("hit"), "i": s("hit"), "g": s("hit"), "o": s("hit"), "t": s("hit")}
    assert puzzle.guessNumber == 1, "it: should not increase guess number"
    assert puzzle.solved

    # TODO: it: should increase streak by one
    stat = get_statistic(1)
    exp = Statistics(
        played=1,
        winRate=100,
        streak=1,
        maxStreak=1,
        distribution=[0, 1, 0, 0, 0, 0]
    )
    assert stat == exp

    # describe: attempt to guess again
    with pytest.raises(WordyError, match="Puzzle is already solved"):
        guess_word(1, "bigot")

    # descrive: load puzzle for a day that has no puzzle
    # it: should raise exception
    # descrive: load future puzzle
    # it: should raise exception

    # -- Simulate moving to the next day. Otherwise, we can not solve a future puzzle.

    # describe: guess next day's puzzle
    # it: should increase streak by one

    # describe: last guess fails
    # describe: last guess succeeds

    # describe: streak broken
    # it: should not affect max streak

    # describe: solve several puzzles in a row
    # it: should increase max streak

    # TODO: Clear cache

    # describe: clear cache and query for puzzle/word data

def test_friends():
    pass

def test_statistics():
    pass

def test_solver():
    pass

