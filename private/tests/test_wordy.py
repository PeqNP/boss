#!/usr/bin/env python3
#
# Tests all game related functions
#

import logging
import pytest

from datetime import datetime, timedelta
from lib import configure_logging
from libtest import *

get_app_module("io.bithead.wordy")
from io.bithead.wordy.lib import *

logging.basicConfig(filename="unittests.log", encoding="utf-8", level=logging.INFO)

def test_game():
    set_randomize_words(False)
    set_dictionary_name("test-dictionary.csv")
    set_database_name("test.sqlite3")
    delete_database()
    start_database()
    current_date = datetime.now().strftime("%m-%d-%Y")
    logging.info(f"Current puzzle date ({current_date})")

    word = get_word(current_date)
    assert word.word == "bigot", "it: should start with the correct word"

    # Scenarios
    # - User lands on page for first time
    #   Should return the daily puzzle
    # - User lands on page after some time, on the same day
    #   Should return the same daily puzzle
    # - User lands on page for second time, on different day, and the puzzle isn't finished
    #   Should show the puzzle they were previously working on
    # - User lands on page for second time, on different day, and the previous day's puzzle is finished
    #   Should show today's puzzle (should automatically move to the next puzzle)

    # describe: get next word to solve
    puzzle = get_current_puzzle(1)
    assert puzzle.id == 1
    assert puzzle.date == current_date, "it: should be today's puzzle"
    assert puzzle.guessNumber == 0
    assert puzzle.attempts == []
    assert puzzle.keys == {}
    assert not puzzle.solved

    daily_puzzle = get_daily_puzzle(1)
    assert puzzle == daily_puzzle, "it: should be the same puzzle as the current puzzle"

    current_puzzle = get_current_puzzle(1)
    assert puzzle == current_puzzle, "it: should return puzzle created earlier"

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

    # it: should increase streak by one
    stat = get_statistics(1)
    exp = Statistics(
        id=1,
        played=1,
        won=1,
        winRate=100,
        currentStreak=1,
        maxStreak=1,
        distribution=[0, 1, 0, 0, 0, 0]
    )
    assert stat == exp

    # describe: attempt to guess again
    with pytest.raises(WordyError, match="Puzzle is already solved"):
        guess_word(1, "bigot")

    # describe: clear cache after guess was cached
    clear_puzzle_cache()

    # it: should load and throw the same error
    with pytest.raises(WordyError, match="Puzzle is already solved"):
        guess_word(1, "bigot")

    # describe: load puzzle for a day that has no puzzle
    previous_date = (datetime.now() - timedelta(days=1)).strftime("%m-%d-%Y")
    with pytest.raises(RecordNotFound):
        get_puzzle_by_date(1, previous_date)

    # describe: load future puzzle
    future_date = (datetime.now() + timedelta(days=1)).strftime("%m-%d-%Y")
    with pytest.raises(WordyError, match="No peaking!"):
        get_puzzle_by_date(1, future_date)

    # -- Simulate moving to the next day. Otherwise, we can not solve a future puzzle.

    # describe: guess next day's puzzle; previous day's puzzle is finished
    # describe: word has a letter that appears more than once
    date_plus_one = (datetime.now() + timedelta(days=1)).strftime("%m-%d-%Y")
    set_current_date(date_plus_one)
    puzzle = get_current_puzzle(1)
    assert puzzle.date == date_plus_one, "it: should automatically move to the next day's puzzle"

    # describe: guess word where second letter is not found
    puzzle = guess_word(1, "halal")
    assert puzzle.attempts == [
        [te("h", "hit"), te("a", "miss"), te("l", "hit"), te("a", "miss"), te("l", "found")]
    ], "it: should find the second letter"
    assert puzzle.keys == {"h": s("hit"), "a": s("miss"), "l": s("hit")}
    assert puzzle.guessNumber == 1
    assert not puzzle.solved

    # describe: guess word where both letters are found
    puzzle = guess_word(1, "lovel")
    assert puzzle.attempts == [
        [te("h", "hit"), te("a", "miss"), te("l", "hit"), te("a", "miss"), te("l", "found")],
        [te("l", "found"), te("o", "found"), te("v", "miss"), te("e", "found"), te("l", "found")],
    ], "it: should return both letters as found"
    assert puzzle.keys == {"h": s("hit"), "a": s("miss"), "l": s("hit"), "v": s("miss"), "e": s("found"), "o": s("found")}
    assert puzzle.guessNumber == 2
    assert not puzzle.solved

    # describe: guess the same word twice
    puzzle = guess_word(1, "lovel")
    # it: should allow user to guess the same word
    # I'm not sure I like this behavior, but this is part of the standard game
    assert puzzle.attempts == [
        [te("h", "hit"), te("a", "miss"), te("l", "hit"), te("a", "miss"), te("l", "found")],
        [te("l", "found"), te("o", "found"), te("v", "miss"), te("e", "found"), te("l", "found")],
        [te("l", "found"), te("o", "found"), te("v", "miss"), te("e", "found"), te("l", "found")],
    ]
    assert puzzle.keys == {"h": s("hit"), "a": s("miss"), "l": s("hit"), "v": s("miss"), "e": s("found"), "o": s("found")}
    assert puzzle.guessNumber == 3
    assert not puzzle.solved

    puzzle = guess_word(1, "lovel")
    puzzle.guessNumber == 4
    puzzle = guess_word(1, "lovel")
    puzzle.guessNumber == 5

    puzzle = guess_word(1, "hello")
    assert puzzle.attempts == [
        [te("h", "hit"), te("a", "miss"), te("l", "hit"), te("a", "miss"), te("l", "found")],
        [te("l", "found"), te("o", "found"), te("v", "miss"), te("e", "found"), te("l", "found")],
        [te("l", "found"), te("o", "found"), te("v", "miss"), te("e", "found"), te("l", "found")],
        [te("l", "found"), te("o", "found"), te("v", "miss"), te("e", "found"), te("l", "found")],
        [te("l", "found"), te("o", "found"), te("v", "miss"), te("e", "found"), te("l", "found")],
        [te("h", "hit"), te("e", "hit"), te("l", "hit"), te("l", "hit"), te("o", "hit")],
    ]
    puzzle.guessNumber == 5
    assert puzzle.solved

    stat = get_statistics(1)
    exp.played = 2
    exp.won = 2
    exp.currentStreak = 2 # it: should increase streak by one
    exp.maxStreak = 2 # it: should increase streak by one
    exp.distribution = [0, 1, 0, 0, 0, 1] # it: should add one to 6th guess
    assert stat == exp

    # describe: last guess fails
    date_plus_two = (datetime.now() + timedelta(days=2)).strftime("%m-%d-%Y")
    set_current_date(date_plus_two)
    puzzle = get_current_puzzle(1)
    assert puzzle.date == date_plus_two, "it: should move to correct date"
    guess_word(1, "fails")
    guess_word(1, "fails")
    guess_word(1, "fails")
    guess_word(1, "fails")
    guess_word(1, "fails")
    puzzle = guess_word(1, "fails")
    assert puzzle.attempts == [
        [te("f", "miss"), te("a", "miss"), te("i", "found"), te("l", "miss"), te("s", "miss")],
        [te("f", "miss"), te("a", "miss"), te("i", "found"), te("l", "miss"), te("s", "miss")],
        [te("f", "miss"), te("a", "miss"), te("i", "found"), te("l", "miss"), te("s", "miss")],
        [te("f", "miss"), te("a", "miss"), te("i", "found"), te("l", "miss"), te("s", "miss")],
        [te("f", "miss"), te("a", "miss"), te("i", "found"), te("l", "miss"), te("s", "miss")],
        [te("f", "miss"), te("a", "miss"), te("i", "found"), te("l", "miss"), te("s", "miss")],
    ]
    puzzle.guessNumber == 5
    assert puzzle.solved is False

    stat = get_statistics(1)
    exp.played = 3 # it: should increase the number of games played
    exp.won = 2 # it: should not add a win
    exp.winRate = 66
    exp.currentStreak = 3 # it: should increase streak by one
    exp.maxStreak = 3 # it: should increase streak by one
    exp.distribution = [0, 1, 0, 0, 0, 1] # it: should not change distribution
    assert stat == exp

    # NOTE: skipping `boned` word

    # describe: break a streak
    date_plus_four = (datetime.now() + timedelta(days=4)).strftime("%m-%d-%Y")
    set_current_date(date_plus_four)
    word = get_word(date_plus_four)
    assert word.word == "moist"

    puzzle = get_current_puzzle(1)
    assert puzzle.word_id == word.id
    assert get_word_by_id(puzzle.word_id) == word
    assert puzzle.date == date_plus_four, "it: should move to correct date"

    puzzle = guess_word(1, "moist")

    assert puzzle.attempts == [
        [te("m", "hit"), te("o", "hit"), te("i", "hit"), te("s", "hit"), te("t", "hit")]
    ]
    assert puzzle.solved
    stat = get_statistics(1)
    exp.played = 4 # it: should increase played games
    exp.won = 3 # it: should add win
    exp.winRate = 75
    exp.currentStreak = 1 # it: should reset current streak
    exp.maxStreak = 3 # it: should not affect max streak
    exp.distribution = [1, 1, 0, 0, 0, 1] # it: should change distribution
    assert stat == exp

    # Increase the max streak
    # describe: solve several puzzles in a row
    next_date = (datetime.now() + timedelta(days=5)).strftime("%m-%d-%Y")
    set_current_date(next_date)
    get_current_puzzle(1)
    guess_word(1, "piper")
    next_date = (datetime.now() + timedelta(days=6)).strftime("%m-%d-%Y")
    set_current_date(next_date)
    get_current_puzzle(1)
    guess_word(1, "bland")
    next_date = (datetime.now() + timedelta(days=7)).strftime("%m-%d-%Y")
    set_current_date(next_date)
    get_current_puzzle(1)
    guess_word(1, "laced")
    next_date = (datetime.now() + timedelta(days=8)).strftime("%m-%d-%Y")
    set_current_date(next_date)
    get_current_puzzle(1)
    guess_word(1, "store")
    # it: should increase max streak
    stat = get_statistics(1)
    exp.played = 8
    exp.won = 7 # it: should add win
    exp.winRate = 87
    exp.currentStreak = 5 # it: should have correct streak
    exp.maxStreak = 5 # it: should increase max streak
    exp.distribution = [5, 1, 0, 0, 0, 1] # it: should change distribution
    assert stat == exp

    # TODO: Clear cache
    # TODO: Streak should NOT be computed for historical days

    # describe: clear cache and query for puzzle/word data

def test_friends():
    pass

def test_statistics():
    pass

def test_solver():
    pass

