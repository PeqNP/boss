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
from lib.server import authenticate_user, get_friends
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

# MARK: Data Models

class Guess(BaseModel):
    word: str

class Solver(BaseModel):
    hits: List[Optional[str]]
    found: List[str]
    misses: List[str]

# MARK: Package

class PossibleWords(BaseModel):
    words: List[str]

# MARK: System

def start():
    logging.info("Starting Wordy...")
    start_database()

def shutdown():
    pass


# MARK: API

router = APIRouter(prefix="/api/io.bithead.wordy")

@router.get("/word", response_model=Puzzle)
async def _get_word(request: Request):
    """ Returns the word of the day.

    This will set the user's puzzle date to today. All subsequent calls
    will relate to this day.
    """
    user = await authenticate_user(request)
    return get_current_puzzle(user.id)

@router.get("/word/{date}", response_model=Puzzle)
async def _get_word_for_date(date: str, request: Request):
    """ Returns the word of the day given a day in YYYY-MM-DD format.

    This will set the user's puzzle date to given date. All subsequent calls
    will relate to this day.
    """
    user = await authenticate_user(request)
    return get_puzzle_by_date(date)

@router.post("/guess", response_model=Attempt)
async def _guess_word(guess: Guess, request: Request):
    """ Attempt to solve the puzzle. """
    user = await authenticate_user(request)
    try:
        puzzle = guess_word(user.id, guess.word)
    except:
        return Attempt(puzzle=None, validGuess=False)
    return Attempt(puzzle=puzzle, validGuess=True)

@router.get("/friends", response_model=FriendResults)
async def _get_friend_results(request: Request):
    """ Return a list of all friends and their results for the given date. """
    user, friends = await get_friends(request)
    results = get_friend_results(user.id, friends)
    return results

@router.get("/statistics", response_model=Statistics)
async def _get_statistics(request: Request):
    """ Return statistical analysis of all games played. """
    user = await authenticate_user(request)
    return get_statistics(user.id)

@router.post("/solve", response_model=PossibleWords)
async def _get_statistics(solver: Solver, request: Request):
    """ Return statistical analysis of all games played. """
    user = await authenticate_user(request)
    return PossibleWords(words=get_possible_words(
        solver.hits,
        solver.found,
        solver.misses
    ))
