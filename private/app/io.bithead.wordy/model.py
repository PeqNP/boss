from datetime import datetime
from enum import Enum, unique
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, List, Optional


class RecordNotFound(Exception):
    pass


# Database models

class Word(BaseModel):
    id: int
    word: str
    date: str

class UserWord(BaseModel):
    id: int
    user_id: int
    word_id: int
    create_date: datetime
    update_date: datetime
    guess_number: int
    attempts: Optional[str]
    keys: Optional[str]
    solved: Optional[bool]

    word: str
    date: str

class UserState(BaseModel):
    id: int
    user_id: int
    user_word_id: int
    word_id: int
    word_date: str
    last_date_played: Optional[str] # MM-DD-YYYY

class Statistic(BaseModel):
    id: int
    user_id: int
    num_played: int
    num_wins: int
    current_streak: int
    max_streak: int
    distribution: str

# Domain models

@unique
class TypedLetterState(Enum):
    # Letter exists, but is in wrong position (yellow)
    FOUND = "found"
    # The letter is in the correct position (green)
    HIT = "hit"
    # Letter does not exist word (gray)
    MISS = "miss"

# Represents a letter that the user has typed.
class TypedLetter(BaseModel):
    # The letter that was typed
    letter: str
    # The state of the letter
    state: TypedLetterState

    model_config = ConfigDict(use_enum_values=True)

class Puzzle(BaseModel): # A user_words
    # user_words.id
    id: int
    # word.id
    wordId: int
    # The date associated to the puzzle e.g. 09/08/2025
    date: str
    # Active guess number. 0-5.
    guessNumber: int
    # The last try's keys that were matched. 0-6 attempts. They are stored
    # in the order that the attempt was made. Therefore, you can use the last
    # `attempts[-1]` element to reveal the last attempt's guess.
    attempts: List[List[TypedLetter]]
    # All keys typed, w/ respective state, while trying to solve this puzzle.
    # key: letter, value: TypedLetterState
    keys: Dict[str, TypedLetterState]
    # Determines the state of the puzzle. No more guesses will be accepted if
    # value is not None.
    #
    # True = Success
    # False = Failed
    # None = In progress
    solved: Optional[bool]

    # FIXME: starlette is having a heart attack because this exists
    model_config = ConfigDict(use_enum_values=True)

class Attempt(BaseModel):
    # Puzzle state
    puzzle: Optional[Puzzle]
    # Indicates that a valid guess was provided. This is True when provided
    # with a 5 letter word that exists in the dictionary.
    validGuess: bool

class FriendResult(BaseModel):
    userId: int
    name: str
    avatarUrl: Optional[str]
    numGuesses: int
    solved: Optional[bool]

class FriendResults(BaseModel):
    puzzleNumber: int
    puzzleDate: str
    results: List[FriendResult]

class Statistics(BaseModel):
    # statistics.id
    id: Optional[int]
    played: int
    won: int
    winRate: int
    currentStreak: int
    maxStreak: int
    # Guess distribution starting with the number of times 1 guess finished the
    # puzzle to 6 guesses to finishe the puzzle.
    distribution: List[int]
