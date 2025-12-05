#
# Database layer
#

import csv
import logging
import os
import random
import sqlite3
from typing import List, Any, Optional

from lib import get_config
from datetime import datetime, timedelta
from .model import *


def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s.decode('utf-8'))

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

# Library

# Randomize words when put in the databse. Default is true. This is set to
# False in test.
RANDOMIZE_WORDS = True
USING_DEFAULT_DB = True
# The default dictionary that contains all words to insert into database
# upon installation.
DICTIONARY_NAME = "dictionary.csv"
# The default Wordy db name
DB_NAME = "wordy.sqlite3"
# All words are stored in a single byte string. This is done to mitigate
# using too much memory. This service shares memory with all other apps and
# the main boss binary.
WORDS = b''
# Total number of words in database
NUM_WORDS = 0
# All words are 5 characters long. This isn't necessary. However, it makes
# it more readable as it avoids a magic number, that may not be obvious.
WORD_LEN = 5

def set_randomize_words(randomize: bool):
    global RANDOMIZE_WORDS
    RANDOMIZE_WORDS = randomize

def set_dictionary_name(name: str):
    """ Set the dictionary to a different name.

    It is assumed that this will only be called during testing. While testing,
    the same dictionary file is used for simplicity.
    """
    global DICTIONARY_NAME
    DICTIONARY_NAME = name

def set_database_name(name: str):
    global DB_NAME
    DB_NAME = name

def get_dictionary_path() -> str:
    """ Return path to dictionary.csv. """
    path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(path, DICTIONARY_NAME)
    return path

def get_db_path() -> str:
    cfg = get_config()
    return os.path.join(cfg.db_path, DB_NAME)

def delete_database():
    path = get_db_path()
    if os.path.isfile(path):
        os.unlink(path)

def get_conn():
    """ Get connection to wordy database. """
    path = get_db_path()
    logging.debug(f"Wordy database path ({path})")
    conn = sqlite3.connect(path)
    return conn

def select(query: str, params: Optional[tuple]=None) -> List[Any]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records

def update(query: str, params: tuple):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    num_rows_affected = cursor.rowcount
    cursor.close()
    conn.close()
    if num_rows_affected < 0:
        raise Exception(f"No records were updated with query ({query}) params ({params})")

def insert(query: str, params: tuple) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rowid = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return rowid

def get_db_version(conn) -> tuple[int, int, int]:
    """ Get current database version.

    Returns:
        `tuple[int]` if version exists e.g. `(1, 0, 0)`. `None` if db is not yet created.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT version
            FROM versions
            ORDER BY id DESC
            LIMIT 1
        """)
        latest_version = cursor.fetchone()
    except:
        return None
    if not latest_version: # Should never happen
        raise Exception("Could not query for the latest version of Wordy database. This is a fatal error.")
    ver = [int(v) for v in latest_version[0].split(".")]
    return tuple(ver)

def create_version_1_0_0(conn, version):
    if version is not None:
        return

    dict_path = get_dictionary_path()
    if not os.path.isfile(dict_path):
        raise Exception("Can not find dictionary CSV at ({dict_path})")

    logging.info("Installing db v1.0.0 - Dictionary @ ({dict_path})")

    cursor = conn.cursor()

    cursor.execute("BEGIN TRANSACTION")

    # Track version of database
    cursor.execute("""
        CREATE TABLE versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            create_date TIMESTAMP NOT NULL
        )
    """)

    # Word of the day
    # date = MM/YY/DDDD
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            word TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_words_date ON words (date)
    """)
    cursor.execute("""
        CREATE INDEX idx_words_word ON words (word)
    """)

    # A relationship between a user and the word of the day
    cursor.execute("""
        CREATE TABLE user_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            create_date TIMESTAMP NOT NULL,
            update_date TIMESTAMP NOT NULL,
            guess_number INT NOT NULL DEFAULT 0,
            attempts TEXT,
            keys TEXT,
            solved BOOL DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_user_words_user_id ON user_words (user_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_user_words_word_id ON user_words (word_id)
    """)

    # Tracks the last puzzle interacted with by user. This helps backend
    # know which puzzle to show the user.
    cursor.execute("""
        CREATE TABLE user_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_word_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            word_date TEXT NOT NULL,
            last_date_played TEXT DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_user_states_user_id ON user_states (user_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_user_states_user_word_id ON user_states (user_word_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_user_states_word_id ON user_states (word_id)
    """)

    # Tracks user solve statistics.
    cursor.execute("""
        CREATE TABLE statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            num_played INT NOT NULL DEFAULT 0,
            num_wins INT NOT NULL DEFAULT 0,
            current_streak INT NOT NULL DEFAULT 0,
            max_streak INT NOT NULL DEFAULT 0,
            distribution TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_statistics_user_id ON statistics (user_id)
    """)

    cursor.execute("""
        INSERT INTO versions (version, create_date)
        VALUES (?, ?)
    """, ("1.0.0", datetime.now()))

    curr_date = datetime.now() # For testing historical days: - timedelta(days=5)
    with open(dict_path, "r") as fh:
        reader = csv.reader(fh)
        words = [row[0] for row in reader]

    if RANDOMIZE_WORDS:
        random.shuffle(words)
    for i, word in enumerate(words):
        d = curr_date + timedelta(days=i)
        d = d.strftime("%m-%d-%Y")
        cursor.execute("""
            INSERT INTO words (date, word)
            VALUES (?, ?)
        """, (d, word))

    conn.commit()
    cursor.close()

    return (1, 0, 0)

def start_database():
    """ Start the database by creating and updating, as necessary.

    Returns:
        Connection to database.
    """
    conn = get_conn()
    ver = get_db_version(conn)
    logging.info(f"Database version ({ver})")
    ver = create_version_1_0_0(conn, ver)
    conn.close()
    cache_words()

def cache_words() -> [str]:
    """ Cache all database words. """
    global WORDS, NUM_WORDS
    rows = select("SELECT word FROM words ORDER BY word")
    NUM_WORDS = len(rows)
    WORDS = b''.join(r["word"].encode("ascii") for r in rows)

def get_word(date: str) -> Word:
    """ Get word for `date`. """
    rows = select("SELECT * FROM words WHERE date = ?", (date,))
    if len(rows) != 1:
        raise RecordNotFound(f"words record for date ({date}) not found")
    return Word(**rows[0])

def get_word_by_id(word_id: int) -> Word:
    """ Get word by its record ID. """
    rows = select("SELECT * FROM words WHERE id = ?", (word_id,))
    if len(rows) != 1:
        raise RecordNotFound(f"words record for ID ({word_id}) not found")
    return Word(**rows[0])

def is_word(word: str) -> bool:
    """ Check if `word` is in database of words. """
    word_bytes = word.encode('ascii')
    # Find insertion point
    lo, hi = 0, NUM_WORDS
    while lo < hi:
        mid = (lo + hi) // 2
        start = mid * WORD_LEN
        mid_word = WORDS[start:start + WORD_LEN]
        if mid_word < word_bytes:
            lo = mid + 1
        else:
            hi = mid
    # Check if match at insertion point
    start = lo * WORD_LEN
    return WORDS[start:start + WORD_LEN] == word_bytes

def get_user_state(user_id: int) -> UserState:
    rows = select("""
        SELECT * FROM user_states WHERE user_id = ?
    """, (user_id,))
    if len(rows) != 1:
        raise RecordNotFound(f"user_states record for user ID ({user_id}) not found")
    return UserState(**rows[0])

def get_user_word(user_word_id: int) -> UserWord:
    rows = select("""
        SELECT
            uw.*,
            w.word,
            w.date
        FROM
            user_words uw JOIN words w ON w.id = uw.word_id
        WHERE
            uw.id = ?
    """, (user_word_id,))
    if len(rows) != 1:
        raise RecordNotFound(f"user_words record for ID ({user_word_id}) not found")
    record = UserWord(**rows[0])
    return record

def get_user_word_by_date(user_id: int, date: str) -> UserWord:
    rows = select("""
        SELECT
            uw.*,
            w.word,
            w.date
        FROM
            user_words uw JOIN words w ON w.id = uw.word_id
        WHERE
            uw.user_id = ?
            AND w.date = ?
    """, (user_id, date))
    if len(rows) != 1:
        raise RecordNotFound(f"user_words record for user ID ({user_id}) date ({date}) not found")
    return UserWord(**rows[0])

def get_first_unfinished_word(user_id: int, date: str) -> tuple[Optional[UserWord], Optional[Word]]:
    """ Returns the first user_word/word that has not been finished.

    UserWord is None if earlier Word found.
    UserWord is not None, when the next puzzle to work on is unfinished.
    """
    rows = select("""
        SELECT
            uw.*,
            w.id AS word_word_id,
            w.word,
            w.date
        FROM
            words w LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
        WHERE
            w.id <= (SELECT id FROM words WHERE date = ?)
            AND uw.solved IS NULL
        ORDER BY w.id DESC LIMIT 1
    """, (user_id, date))
    # NOTE: `uw.solved is NULL` accounts for both
    # - There is no corresponding `user_word` for word
    # - There is a corresponding `user_word` for word, but the puzzle is not finished
    if len(rows):
        row = rows[0]
        word = {
            "id": row["word_word_id"],
            "word": row["word"],
            "date": row["date"]
        }
        word = Word(**word)
        if row["user_id"] is None:
            return (None, word)
        else:
            row = dict(row)
            del row["word_word_id"]
            user_word = UserWord(**row)
            return (user_word, word)
    else:
        raise RecordNotFound(f"User ({user_id}) has finished all past puzzles")

def get_oldest_user_word(user_id: int) -> tuple[Optional[UserWord], Optional[Word]]:
    """ Returns the first unsolved puzzle or the very first word that the
    user has not played.

    NOTE: If there is no unfinished puzzle, this will return the first word
    record that is closest to the last played date. The user_word record
    will be `None`! This is date you can use to load the next record.
    """
    # NOTE: Users may have breaks in their days
    rows = select("""
        SELECT
            uw.*,
            w.word,
            w.date
        FROM
            user_words uw JOIN words w ON w.id = uw.word_id
        WHERE
            uw.user_id = ?
            AND uw.solved IS NULL
        ORDER BY w.id DESC LIMIT 1
    """, (user_id,))
    if len(rows):
        user_word = UserWord(**rows[0])
        return (user_word, None)
    # Find the first word in the past that the user has not played.
    # NOTE: This uses `<` because the above logic should return previous
    # puzzle if it was today.
    # NOTE: Checking w.id w/ last MAX(word_id) as words are inserted into
    # the database in sequential order.
    # NOTE: If SELECT MAX(word_id) returns NULL, this will return no records.
    # This is necessary if user has never solved a puzzle.
    rows = select("""
        SELECT
            w.*
        FROM
            words w LEFT JOIN user_words uw ON w.id = uw.word_id AND uw.user_id = ?
        WHERE
            w.id < (SELECT MAX(word_id) FROM user_words WHERE user_id = ?)
            AND uw.user_id IS NULL
        ORDER BY w.id DESC LIMIT 1
    """, (user_id, user_id))
    if len(rows):
        word = Word(**rows[0])
        return (None, word)
    else:
        # Never played a puzzle
        raise RecordNotFound(f"Last word record for user ID ({user_id})")

def insert_user_word(user_id: int, word_id: int) -> int:
    return insert("""
        INSERT INTO user_words (user_id, word_id, create_date, update_date)
        VALUES (?, ?, ?, ?)
    """, (user_id, word_id, datetime.now(), datetime.now()))

def update_user_word(user_word_id: int, guess_number: int, attempts: str, keys: str, solved: Optional[bool]) -> int:
    return update("""
        UPDATE user_words SET
            update_date = ?,
            guess_number = ?,
            attempts = ?,
            keys = ?,
            solved = ?
        WHERE
            id = ?
    """, (datetime.now(), guess_number, attempts, keys, solved, user_word_id))

def insert_user_state(user_id: int, user_word_id: int, word_id: int, word_date: str) -> int:
    return insert("""
        INSERT INTO user_states (user_id, user_word_id, word_id, word_date)
        VALUES (?, ?, ?, ?)
    """, (user_id, user_word_id, word_id, word_date))

def update_user_state(user_id: int, user_word_id: int, word_id: int, word_date: str) -> int:
    return update("""
        UPDATE
            user_states
        SET
            user_word_id = ?,
            word_id = ?,
            word_date = ?
        WHERE user_id = ?
    """, (user_word_id, word_id, word_date, user_id))

def update_user_state_last_played_date(user_id: int, last_date_played: str):
    return update("""
        UPDATE user_states SET last_date_played = ?
        WHERE user_id = ?
    """, (last_date_played, user_id))

def get_statistic(user_id: int) -> Statistic:
    rows = select("""
        SELECT * FROM statistics WHERE user_id = ?
    """, (user_id,))
    if len(rows) != 1:
        raise RecordNotFound(f"statistics record for user ID ({user_id}) not found")
    return Statistic(**rows[0])

def insert_statistic(user_id: int, num_played: int, num_wins: int, streak: int, max_streak: int, distribution: str):
    return insert("""
        INSERT INTO statistics (user_id, num_played, num_wins, current_streak, max_streak, distribution)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, num_played, num_wins, streak, max_streak, distribution))

def update_statistic(statistic_id: int, num_played: int, num_wins: int, streak: int, max_streak: int, distribution: str):
    update("""
        UPDATE statistics SET
            num_played = ?,
            num_wins = ?,
            current_streak = ?,
            max_streak = ?,
            distribution = ?
        WHERE
            id = ?
    """, (num_played, num_wins, streak, max_streak, distribution, statistic_id))

def upsert_user_state(user_id: int, user_word_id: int, word_id: int, word_date: str) -> UserState:
    try:
        state = get_user_state(user_id)
    except:
        insert_user_state(user_id, user_word_id, word_id, word_date)
        return get_user_state(user_id)
    update_user_state(user_id, user_word_id, word_id, word_date)
    state.user_word_id = user_word_id
    return state

def get_friend_user_words(word_id: int, friend_user_ids: List[int]) -> List[UserWord]:
    """ Get state of all friend's for a given word. """
    rows = select(f"""
        SELECT
            uw.*,
            w.word,
            w.date
        FROM
            user_words uw JOIN words w ON w.id = uw.word_id
        WHERE
            word_id = ?
            AND user_id IN ({', '.join('?' * len(friend_user_ids))})
    """, tuple([word_id] + friend_user_ids))
    return [UserWord(**row) for row in rows]

def get_possible_words(hits: List[Optional[str]], found: List[str], misses: List[str]) -> List[str]:
    pattern = ''
    params = []
    for h in hits:
        if h is not None:
            pattern += h
        else:
            pattern += '_'

    query = "SELECT word FROM words WHERE "
    where = []

    if len(pattern) > 0:
        where.append("word LIKE ?")
        params.append(pattern)

    # Add conditions for found letters (must contain each)
    for f in set(found):  # Use set to handle possible duplicates, but assume unique for simplicity
        where.append("word LIKE ?")
        params.append(f'%{f}%')

    # Add conditions for miss letters (must not contain any)
    for m in misses:
        where.append("word NOT LIKE ?")
        params.append(f'%{m}%')

    query += " AND ".join(where)
    rows = select(query, params)
    results = [row[0] for row in rows]
    return results
