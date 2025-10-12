#
# Wordy - A Wordle(TM)-like game.
#
# This is a state machine that tracks the puzzle date by user.
#
# When the user first queries for either `/word`, or `/word/{date}`, the
# user's state will be configured to work on that specific puzzle's date.
#
# Calls to `/guess/{word}`, `/friends`, etc. will use this date.
#

import asyncio
import logging

from .db import start_database
from .model import *
from .lib import *
from lib.server import authenticate_user
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

# MARK: Data Models

class Guess(BaseModel):
    word: str

# MARK: Package


# MARK: System

def start():
    logging.info("Starting Wordy...")
    start_database()

def shutdown():
    pass


# MARK: API

router = APIRouter(prefix="/api/io.bithead.wordy")

@router.get("/word", response_model=Puzzle)
async def get_word(request: Request):
    """ Returns the word of the day.

    This will set the user's puzzle date to today. All subsequent calls
    will relate to this day.
    """
    user = await authenticate_user(request)
    return get_current_puzzle(user.id)

@router.get("/word/{date}", response_model=Puzzle)
async def get_word_for_date(date: str, request: Request):
    """ Returns the word of the day given a day in YYYY-MM-DD format.

    This will set the user's puzzle date to given date. All subsequent calls
    will relate to this day.
    """
    user = await authenticate_user(request)
    return get_puzzle_by_date(date)

@router.post("/guess", response_model=Attempt)
async def guess_word(guess: Guess, request: Request):
    """ Attempt to solve the puzzle. """
    user = await authenticate_user(request)
    return guess_word(user.id, guess.word)

@router.get("/friends", response_model=FriendResults)
async def get_friend_results(request: Request):
    """ Return a list of all friends and their results for the given date. """
    # TODO: Load friend results
    user = await authenticate_user(request)
    return FriendResults(
        puzzleNumber=1430,
        puzzleDate="10/07/2025",
        results=[FriendResult(
            id=5,
            name="Tristan",
            avatarUrl="/boss/app/io.bithead.wordy/img/solver.svg",
            numGuesses=3,
            finished=True
        )]
    )
    # TODO: Create `None` avatarUrl and show placeholder

@router.get("/statistics", response_model=Statistics)
async def get_statistics(request: Request):
    """ Return statistical analysis of all games played. """
    user = await authenticate_user(request)
    return get_statistics(user.id)
