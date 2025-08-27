#
# Wordy - A Wordle(TM)-like game.
#

import asyncio
import logging

from .db import start_database
from enum import Enum, unique
from lib.server import authenticate_user
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any, List, Optional

# MARK: Data Models

@unique
class TypedLetterState(Enum):
    # Letter exists, but is in wrong position (yellow)
    EXISTS = "exists"
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

class SolveAttempt(BaseModel):
    # The list of letters typed. Always six letters. The position of the letters
    # matches the order they were typed in.
    value: List[TypedLetter]

# The word for the respective day
class WordOfTheDay(BaseModel):
    # The attempts taken to solve the word
    attempts: List[SolveAttempt]
    # The letters that have been tried
    typed_letters: List[TypedLetter]
    # User has completed word puzzle
    completed: bool

# MARK: Package


# MARK: System

def start():
    logging.info("Starting Wordsy...")
    start_database()

def shutdown():
    pass


# MARK: API

router = APIRouter(prefix="/api/io.bithead.wordy")

@router.get("/word", response_model=WordOfTheDay)
async def get_word(request: Request):
    """ Returns the word of the day. """
    user = await authenticate_user(request)
    check_user(user_id, user)
    return WordOfTheDay(attempts=[], typed_letters=[], completed=False)

@router.get("/word/{date}", response_model=WordOfTheDay)
async def get_word_for_date(date: str, request: Request):
    """ Returns the word of the day given a day in YYYY-MM-DD format. """
    user = await authenticate_user(request)
    check_user(user_id, user)
    return WordOfTheDay(attempts=[], typed_letters=[], completed=False)

@router.get("/attempt/{word}", response_model=WordOfTheDay)
async def delete_default(word: str, request: Request):
    """ Attempt to solve the puzzle. """
    # TODO: Word must be six characters long
    # TODO: Word must exist in database. Otherwise, it is an invalid try.
    # TODO: Match word and provide new WordOfTheDay state
    user = await authenticate_user(request)
    check_user(user_id, user)
    return WordOfTheDay(attempts=[], typed_letters=[], completed=False)
