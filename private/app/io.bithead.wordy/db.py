#
# Database layer
#

import csv
import logging
import os
import random
import sqlite3
from typing import List, Any

from lib import get_config
from datetime import datetime, timedelta
from .model import *

DB_NAME = "wordsy.sqlite3"

def set_database_name(name: str):
    global DB_NAME
    DB_NAME = name

def get_dictionary_path() -> str:
    """ Return path to dictionary.csv. """
    path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(path, "dictionary.csv")
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
    return cursor.fetchall()

def insert(query: str, params: tuple) -> int:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.lastrowid


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
            solved BOOL
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

    cursor.execute("""
        INSERT INTO versions (version, create_date)
        VALUES (?, ?)
    """, ("1.0.0", datetime.now()))

    curr_date = datetime.now()
    with open(dict_path, "r") as fh:
        reader = csv.reader(fh)
        words = [row[0] for row in reader]

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

def get_word(date: str) -> Word:
    rows = select("SELECT * FROM words WHERE date = ?", (date,))
    if len(rows) != 1:
        raise RecordNotFound(f"word record for date ({date}) not found")
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
        raise RecordNotFound(f"user_state record for user ID ({user_id}) not found")
    return UserWord(**rows[0])

def insert_user_word(user_id: int, word_id: int):
    insert("""
        INSERT INTO user_words (user_id, word_id, create_date, update_date)
        VALUES (?, ?, ?, ?)
    """, (user_id, word_id, datetime.now(), datetime.now()))
