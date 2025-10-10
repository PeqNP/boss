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

RANDOMIZE_WORDS = True
DICTIONARY_NAME = "dictionary.csv"
DB_NAME = "wordsy.sqlite3"

def set_randomize_words(randomize: bool):
    global RANDOMIZE_WORDS
    RANDOMIZE_WORDS = randomize

def set_dictionary_name(name: str):
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
    """ Get connection to wordsy database. """
    path = get_db_path()
    logging.info(f"Wordsy database path ({path})")
    conn = sqlite3.connect(path)
    return conn

def select(query: str, params: tuple) -> List[Any]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records

def update(query: str, params: tuple):
    select(query, params)

def insert(query: str, params: tuple) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rowid = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return rowid

def get_db_version(conn) -> str:
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
        raise Exception("Could not query for the latest version of Wordsy database. This is a fatal error.")
    ver = [int(v) for v in latest_version[0].split(".")]
    return tuple(ver)

def create_version_1_0_0(conn, version):
    if version is not None:
        return

    dict_path = get_dictionary_path()
    if not os.path.isfile(dict_path):
        raise Exception("Can not find dictionary CSV at ({dict_path})")

    logging.info("Installing db v1.0.0")

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
            user_word_id INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_user_states_user_id ON user_states (user_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_user_states_user_word_id ON user_states (user_word_id)
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

    curr_date = datetime.now()
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

def get_word(date: str) -> Word:
    rows = select("SELECT * FROM words WHERE date = ?", (date,))
    if len(rows) != 1:
        raise RecordNotFound(f"word record for date ({date}) not found")
    return Word(**rows[0])

def get_word_by_id(word_id: int) -> Word:
    rows = select("SELECT * FROM words WHERE id = ?", (word_id,))
    if len(rows) != 1:
        raise RecordNotFound(f"word record for ID ({word_id}) not found")
    return Word(**rows[0])

def get_user_state(user_id: int) -> UserState:
    rows = select("""
        SELECT
            us.*,
            w.date
        FROM
            user_states us
            JOIN user_words uw ON uw.id = us.user_word_id
            JOIN words w ON w.id = uw.word_id
        WHERE us.user_id = ?
    """, (user_id,))
    if len(rows) != 1:
        raise RecordNotFound(f"user_state record for user ID ({user_id}) not found")
    return UserState(**rows[0])

def get_user_word(user_id: int, date: str) -> UserWord:
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
        raise RecordNotFound(f"user_word record for user ID ({user_id}) date ({date}) not found")
    return UserWord(**rows[0])

def get_user_word_by_id(user_word_id: int) -> UserWord:
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
        raise RecordNotFound(f"user_word record for ID ({user_word_id}) not found")
    return UserWord(**rows[0])

def insert_user_word(user_id: int, word_id: int) -> int:
    logging.debug("Inserting user_word user_id ({user_id}) word_id ({word_id})")
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

def insert_user_state(user_id: int, user_word_id: int) -> int:
    return insert("""
        INSERT INTO user_states (user_id, user_word_id)
        VALUES (?, ?)
    """, (user_id, user_word_id))

def update_user_state(user_id: int, user_word_id: int) -> int:
    return update("""
        UPDATE user_states SET user_word_id = ?
        WHERE user_id = ?
    """, (user_word_id, user_id))

def get_statistic(user_id: int) -> Statistic:
    rows = select("""
        SELECT * FROM statistics WHERE user_id = ?
    """, (user_id,))
    if len(rows) != 1:
        raise RecordNotFound(f"statistic record for user ID ({user_id}) not found")
    return Statistic(**rows[0])

def insert_statistic(user_id: int, num_played: int, num_wins: int, streak: int, max_streak: int, distribution: str):
    return insert("""
        INSERT INTO statistics (user_id, num_played, num_wins, streak, max_streak)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, num_played, num_wins, streak, max_streak))

def update_statistic(user_id: int, num_played: int, num_wins: int, streak: int, max_streak: int, distribution: str):
    update("""
        UPDATE statistics SET
            num_played = ?,
            num_wins = ?,
            streak = ?,
            max_streak = ?,
            distribution = ?
        WHERE
            id = ?
    """, (user_id, num_played, num_wins, streak, max_streak, distribution))

def upsert_user_state(user_id: int, user_word_id: int) -> UserState:
    try:
        state = get_user_state(user_id)
    except:
        insert_user_state(user_id, user_word_id)
        return get_user_state(user_id)
    update_user_state(user_id, user_word_id)
    state.user_word_id = user_word_id
    return state
