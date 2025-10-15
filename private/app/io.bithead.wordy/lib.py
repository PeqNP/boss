#
# Wordy game logic.
#
# This layer is creatd to make it easier to test.
#

import logging
import json

from . import db
from .model import *
from cachetools import TTLCache
from lib.model import Friend
from datetime import datetime, timedelta

WORD_TTL = 60 * 60 * 24 # 24 hours
USER_TTL = 60 * 60 # 1 hour

VALID_CHARS = "abcdefghijklmnopqrstuvwxyz"

# Contains word records alone w/ word analysis (letters that exist in word, etc.)
TARGET_WORDS = TTLCache(1024, ttl=WORD_TTL)

# Contains map of user's current puzzle state
PUZZLES = TTLCache(1024, ttl=USER_TTL)

# Should only be used for testing. This allows the current puzzle date to be shifted
# forwards or backwards in time to test scenarios such as streaks, etc.
CURRENT_DATE = None

def set_current_date(date: str):
    global CURRENT_DATE
    logging.info(f"Setting current date to ({date})")
    CURRENT_DATE = date

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
    if CURRENT_DATE is not None:
        return CURRENT_DATE
    current_date = datetime.now()
    return current_date.strftime("%m-%d-%Y")

def get_previous_date(date: str) -> str:
    date_obj = datetime.strptime(date, "%m-%d-%Y")
    previous_day = date_obj - timedelta(days=1)
    return previous_day.strftime("%m-%d-%Y")

def clear_puzzle_cache():
    global TARGET_WORDS, PUZZLES
    TARGET_WORDS.clear()
    PUZZLES.clear()

def get_current_puzzle(user_id: int) -> Puzzle:
    """ Returns the last puzzle the user was on.

    If the user has already started the Puzzle, it will return the last
    puzzle the user was on.
    """
    try:
        state = db.get_user_state(user_id)
    except RecordNotFound:
        return get_daily_puzzle(user_id)
    # If current puzzle is solved, and puzzle date is not today, move to the
    # daily puzzle.
    user_word = db.get_user_word(state.user_word_id)
    if user_word.solved is not None and user_word.date != get_current_date():
        return get_daily_puzzle(user_id)
    logging.debug(f"Found puzzle for user_id ({user_id}) user_word_id ({state.user_word_id})")
    return make_puzzle(user_id, user_word)

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
    if datetime.strptime(date, "%m-%d-%Y") > datetime.strptime(get_current_date(), "%m-%d-%Y"):
        raise WordyError("No peaking!")
    try:
        user_word = db.get_user_word_by_date(user_id, date)
        logging.debug(f"Found puzzle for user_id ({user_id}) date ({date})")
        return make_puzzle(user_id, user_word)
    except RecordNotFound:
        logging.debug(f"Creating puzzle for user_id ({user_id}) date ({date})")
        return create_puzzle(user_id, date)

def make_puzzle(user_id: int, user_word: UserWord) -> Puzzle:
    """ Make puzzle from db model.

    Making a puzzle effectively effectively sets the user's active puzzle. It is
    expected that all subsequent requests will be to guess the puzzle.
    """
    attempts = user_word.attempts or "[]"
    keys = user_word.keys or "{}"
    puzzle = Puzzle(
        id=user_word.id,
        wordId=user_word.word_id,
        date=user_word.date,
        guessNumber=user_word.guess_number,
        attempts=json.loads(attempts),
        keys=json.loads(keys),
        solved=user_word.solved
    )
    # Set active user puzzle
    PUZZLES[user_id] = puzzle
    db.upsert_user_state(user_id, user_word.id, user_word.word_id, user_word.date)
    return puzzle

def make_statistics(r: Statistic) -> Statistics:
    return Statistics(
        id=r.id,
        played=r.num_played,
        won=r.num_wins,
        winRate=int((r.num_wins / r.num_played) * 100),
        currentStreak=r.current_streak,
        maxStreak=r.max_streak,
        distribution=json.loads(r.distribution)
    )

def save_statistics(user_id: int, puzzle: Puzzle, s: Statistics):
    """ Save statistics.

    This must only be called after a puzzle has been finished. Otherwise, the
    streak counters will be off.
    """
    state = db.get_user_state(user_id)

    # Notes:
    # - last_date_played will always be a date in the past
    # - Streaks are only computed if the puzzle date is today. Solving old
    #   puzzles will not affect streaks.

    if puzzle.date == get_current_date() and (state.last_date_played is None or get_previous_date(puzzle.date) == state.last_date_played):
        s.currentStreak += 1
    elif puzzle.date == get_current_date():
        # Reset streak, but only if finishing today's puzzle. If user is
        # playing a past puzzle, it should not affect the streak.
        s.currentStreak = 1
    if s.currentStreak > s.maxStreak:
        s.maxStreak = s.currentStreak

    if s.id:
        db.update_statistic(
            s.id,
            s.played,
            s.won,
            s.currentStreak,
            s.maxStreak,
            json.dumps(s.distribution)
        )
    else:
        db.insert_statistic(
            user_id,
            s.played,
            s.won,
            s.currentStreak,
            s.maxStreak,
            json.dumps(s.distribution)
        )

def save_puzzle(puzzle: Puzzle):
    d = puzzle.model_dump_json()
    d = json.loads(d)
    db.update_user_word(
        puzzle.id,
        puzzle.guessNumber,
        json.dumps(d["attempts"]),
        json.dumps(d["keys"]),
        puzzle.solved
    )

def create_puzzle(user_id: int, date: str) -> Puzzle:
    """ Create a new puzzle for date. """
    word = db.get_word(date)
    user_word_id = db.insert_user_word(user_id, word.id)
    user_word = db.get_user_word(user_word_id)
    return make_puzzle(user_id, user_word)

def get_cached_puzzle(user_id: int) -> Puzzle:
    """ Get the user's cached puzzle. If cache isn't found, puzzle is loaded
    from database.

    This expects a puzzle to have been created prior to calling this function.
    """
    puzzle = PUZZLES.get(user_id, None)
    if puzzle is None:
        logging.debug("Cache miss for user puzzle ({user_id})")
        # NOTE: User state, and user word, should have been created at this point
        state = db.get_user_state(user_id)
        user_word = db.get_user_word(state.user_word_id)
        puzzle = make_puzzle(user_id, user_word)
    return puzzle

def guess_word(user_id: int, word: str) -> Puzzle:
    word = word.lower()
    for char in word:
        if char not in VALID_CHARS:
            raise WordyError("Word must contain characters 'A' through 'Z' only")

    if len(word) != 5:
        raise WordyError("Word must be 5 characters long")

    if not db.is_word(word):
        raise WordyError("Word does not exist")

    puzzle = get_cached_puzzle(user_id)

    if puzzle.solved is not None:
        raise WordyError("Puzzle is already solved")

    target = TARGET_WORDS.get(puzzle.wordId, None)
    if target is None:
        _word = db.get_word_by_id(puzzle.wordId)
        analysis = {}
        for char in _word.word:
            if analysis.get(char, None):
                analysis[char] += 1
            else:
                analysis[char] = 1
        target = TargetWord(word=_word, analysis=analysis)
        TARGET_WORDS[_word.id] = target

    if word == target.word.word:
        attempt = []
        for letter in word:
            puzzle.keys[letter] = TypedLetterState.HIT
            attempt.append(TypedLetter(letter=letter, state=TypedLetterState.HIT))
        puzzle.attempts.append(attempt)
        puzzle.solved = True

        save_puzzle(puzzle)
        PUZZLES[user_id] = puzzle

        stat = get_statistics(user_id)
        stat.played += 1
        stat.won += 1
        stat.distribution[puzzle.guessNumber] += 1
        save_statistics(user_id, puzzle, stat)

        db.update_user_state_last_played_date(user_id, puzzle.date)

        return puzzle

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

    for idx, letter in enumerate(word):
        # Letter appears more than once in guess
        if pressedKeys.get(letter, None):
            pressedKeys[letter] += 1;
        # First time it appears in guess
        else:
            pressedKeys[letter] = 1;

        # If letter in position matches letter in respective word position, it hits
        if letter == target.word.word[idx]:
            keys[letter] = TypedLetterState.HIT
            matches.append(TypedLetter(
                letter=letter,
                state=TypedLetterState.HIT
            ))
        # If it's somewhere in the word, it may be found, or a miss (if appearing less than typed)
        elif letter in target.word.word:
            # Letter appears more than once (the number of times repeated in analysis)
            if pressedKeys[letter] <= target.analysis[letter]:
                if keys.get(letter, None) is None:
                    keys[letter] = TypedLetterState.FOUND
                matches.append(TypedLetter(
                  letter=letter,
                  state=TypedLetterState.FOUND
                ))
            # Letter no longer appears
            else:
                if keys.get(letter, None) is None:
                    keys[letter] = TypedLetterState.MISS
                matches.append(TypedLetter(
                  letter=letter,
                  state=TypedLetterState.MISS
                ))
        # Letter not found in word
        else:
            keys[letter] = TypedLetterState.MISS
            matches.append(TypedLetter(
              letter=letter,
              state=TypedLetterState.MISS
            ))

    puzzle.attempts.append(matches)
    if puzzle.guessNumber == 5:
        puzzle.solved = False

        stat = get_statistics(user_id)
        stat.played += 1
        save_statistics(user_id, puzzle, stat)

        db.update_user_state_last_played_date(user_id, puzzle.date)
    else:
        puzzle.guessNumber += 1

    save_puzzle(puzzle)
    PUZZLES[user_id] = puzzle

    return puzzle

def get_statistics(user_id: int) -> Statistics:
    try:
        stat = db.get_statistic(user_id)
        return make_statistics(stat)
    except RecordNotFound:
        pass
    return Statistics(
        id=None,
        played=0,
        won=0,
        winRate=0,
        currentStreak=0,
        maxStreak=0,
        distribution=[0, 0, 0, 0, 0, 0]
    )

def get_friend_results(user_id: int, friends: [Friend]) -> FriendResults:
    try:
        state = db.get_user_state(user_id)
    except:
        # Don't return anything if the user hasn't yet played a puzzle.
        # This should not be possible, as the first page the user lands on is
        # the puzzle page. A state should have already been created at this time.
        return []
    results = []
    user_words = db.get_friend_user_words(state.word_id, [friend.userId for friend in friends])
    for friend in friends:
        uw = next((x for x in user_words if x.user_id == friend.userId), None)
        if uw is None:
            results.append(FriendResult(
                userId=friend.userId,
                name=friend.name,
                avatarUrl=friend.avatarUrl,
                numGuesses=0,
                solved=None
            ))
        else:
            logging.info(f"uw ({uw})")
            results.append(FriendResult(
                userId=friend.userId,
                name=friend.name,
                avatarUrl=friend.avatarUrl,
                numGuesses=len(json.loads(uw.attempts)),
                solved=uw.solved
            ))
    return FriendResults(
        puzzleNumber=state.word_id,
        puzzleDate=state.word_date,
        results=results
    )

def get_possible_words(hits: List[Optional[str]], found: List[str], misses: List[str]) -> List[str]:
    """ Get list of possible words based on hit|found|missed letters. """
    for char in hits:
        if char is not None and char not in VALID_CHARS:
            raise WordyError("Hit characters must contain characters 'A' through 'Z' only")
    for char in found:
        if char is not None and char not in VALID_CHARS:
            raise WordyError("Found characters must contain characters 'A' through 'Z' only")
    for char in misses:
        if char is not None and char not in VALID_CHARS:
            raise WordyError("Missed characters must contain characters 'A' through 'Z' only")

    return db.get_possible_words(hits, found, misses)
