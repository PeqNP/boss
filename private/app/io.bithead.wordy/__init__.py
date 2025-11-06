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
from lib.model import User
from lib.server import get_friends, require_user
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Annotated, List, Optional

# MARK: Data Models

class Guess(BaseModel):
    word: str

class Solver(BaseModel):
    hits: List[Optional[str]]
    found: List[str]
    misses: List[str]

class PossibleWords(BaseModel):
    words: List[str]

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
@require_user()
async def _word(boss_user: User, request: Request):
    """ Returns the word of the day.

    This returns the last puzzle the user was playing or the current puzzle.
    All subsequent calls will query the same puzzle.
    """
    return get_current_puzzle(boss_user.id)

@router.get("/word/{date}", response_model=Puzzle)
@require_user()
async def _word_date(date: str, boss_user: User, request: Request):
    """ Returns the word of the day given a day in YYYY-MM-DD format.

    This will set the user's puzzle date to given date. All subsequent calls
    will relate to this day.
    """
    return get_puzzle_by_date(boss_user.id, date)

@router.get("/past-word", response_model=Puzzle)
@require_user()
async def _past_word(boss_user: User, request: Request):
    """ Returns the first word in the past that has not yet been played.

    This will set the user's puzzle date to date associated to puzzle.
    """
    return get_first_unfinished_puzzle(boss_user.id)

@router.post("/guess", response_model=Attempt)
@require_user()
async def _guess(guess: Guess, boss_user: User, request: Request):
    """ Attempt to solve the puzzle. """
    try:
        puzzle = guess_word(boss_user.id, guess.word)
    except:
        return Attempt(puzzle=None, validGuess=False)
    return Attempt(puzzle=puzzle, validGuess=True)

@router.get("/friends", response_model=FriendResults)
async def _friends(request: Request):
    """ Return a list of all friends and their results for the given date. """
    user, friends = await get_friends(request)
    results = get_friend_results(user.id, friends)
    return results

@router.get("/statistics", response_model=Statistics)
@require_user()
async def _statistics(boss_user: User, request: Request):
    """ Return statistical analysis of all games played. """
    return get_statistics(boss_user.id)

@router.post("/solve", response_model=PossibleWords)
async def _solve(solver: Solver, request: Request):
    """ Return statistical analysis of all games played. """
    return PossibleWords(words=get_possible_words(
        solver.hits,
        solver.found,
        solver.misses
    ))
