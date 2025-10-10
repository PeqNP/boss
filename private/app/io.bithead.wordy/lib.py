#
# Wordy game logic.
#
# This layer is creatd to make it easier to test.
#

import json

from .db import *
from .model import *
from cachetools import TTLCache
from datetime import datetime

WORD_TTL = 60 * 60 * 24 # 24 hours
USER_TTL = 60 * 60 # 1 hour

# Contains word records alone w/ word analysis (letters that exist in word, etc.)
TARGET_WORDS = TTLCache(1024, ttl=WORD_TTL)

# Contains map of user's current puzzle state
USER_STATES = TTLCache(1024, ttl=USER_TTL)

class TargetWord(BaseModel):
    # The word to guess
    word: Word
    # Contains analysis for word being guessed
    # key is letter, the value the number of times the letter is in the word
    analysis: dict

class PuzzleState(BaseModel):
    id: int

class WordyError(Exception):
    pass

def get_current_date() -> str:
    current_date = datetime.now()
    return current_date.strftime("%m-%d-%Y")

def get_current_puzzle(user_id: int) -> Puzzle:
    """ Returns the last puzzle the user was on.

    If the user has already started the Puzzle, it will return the current
    user's state.
    """
    try:
        state = get_user_state(user_id)
    except RecordNotFound:
        return get_daily_puzzle(user_id)
    return get_puzzle_by_date(user_id, state.date)

def get_daily_puzzle(user_id: int) -> Puzzle:
    """ Returns the current day's puzzle.

    If the user has already started the Puzzle, it will return the current
    user's state.
    """
    return get_puzzle_by_date(user_id, get_current_date())

def get_puzzle_by_date(user_id: int, date: str) -> Puzzle:
    """ Returns puzzle for specified date.

    If the user has already started the Puzzle, it will return the current
    user's state.
    """
    try:
        user_word = get_user_word(user_id, date)
    except RecordNotFound:
        return create_puzzle(user_id, date)

def make_puzzle(user_word: UserWord) -> Puzzle:
    attempts = user_word.attempts or "[]"
    keys = user_word.keys or "{}"
    return Puzzle(
        id=user_word.id,
        word_id=user_word.word_id,
        date=user_word.date,
        guessNumber=user_word.guess_number,
        attempts=json.loads(attempts),
        keys=json.loads(keys),
        solved=user_word.solved == 1
    )

def create_puzzle(user_id: int, date: str) -> Puzzle:
    word = get_word(date)
    insert_user_word(user_id, word.id)
    user_word = get_user_word(user_id, date)
    upsert_user_state(user_id, user_word.id)
    return make_puzzle(user_word)

def guess_word(user_id: int, word: str) -> Puzzle:
    if len(word) != 5:
        raise WordyError("Word must be 5 characters long")

    puzzle = USER_STATES.get(user_id, None)
    if not puzzle:
        # TODO: Load the puzzle state
        # TODO: If puzzle state doesn't exist, raise error
        pass

    target = TARGET_WORDS.get(puzzle.word_id, None)
    if target is None:
        # TODO: Load word
        # TODO: Raise error if word doesn't exist
        pass

    # 1:1 match with letter column. Contains state for each letter in
    # respective location.
    # Where HELLO = position 012345, respectively
    matches = []
    # Pressed keys tracks the key, and the number of times it was pressed
    # for this spcific guess. Using the above example:
    # H = 1
    # E = 1
    # L = 2
    # O = 1
    # When a letter appears more than once, but in the wrong location, this
    # ensures the 2nd letter is shown as "found" instead of a "miss."
    pressedKeys = {}

    # TODO: When going from found to hit, it goes one way. Such that A in the
    # wrong spot will turn to A in right spot. But never the other way around.
    keys = puzzle.keys

    for idx, letter in word.enumerate():
        # Letter appears more than once in guess
        if pressedKeys.get(letter, None):
            pressedKeys[letter] += 1;
        # First time it appears in guess
        else:
            pressedKeys[letter] = 1;

        # If letter in position matches letter in respective word position, it hits
        if letter == target.word[idx]:
            keys[letter] = TypedLetterState.HIT
            matches[idx] = {
                "letter": letter,
                "state": TypedLetterState.HIT
            }
        # If it's somewhere in the word, it may be found, or a miss (if appearing less than typed)
        elif letter in target.word:
            # Letter appears more than once (the number of times repeated in analysis)
            if pressedKeys[letter] <= target.analysis[letter]:
                if key.get(letter, None) is None:
                    keys[letter] = TypedLetterState.FOUND
                matches[idx] = {
                  "letter": letter,
                  "state": TypedLetterState.FOUND
                }
            # Letter no longer appears
            else:
                if key.get(letter, None) is None:
                    keys[letter] = TypedLetterState.MISS
                matches[idx] = {
                  "letter": letter,
                  "state": TypedLetterState.MISS
                }
        # Letter not found in word
        else:
            keys[letter] = TypedLetterState.MISS
            matches[idx] = {
              "letter": letter,
              "state": TypedLetterState.MISS
            }

    if puzzle.guessNumber == 5:
        puzzle.solved = False
    else:
        puzzle.guessNumber += 1

    # TODO: Save

    return puzzle
