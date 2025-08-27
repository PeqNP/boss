
import csv
import logging
import os
import random
import sqlite3

from lib import get_config
from datetime import datetime, timedelta

def get_dictionary_path() -> str:
    """ Return path to dictionary.csv. """
    path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(path, "dictionary.csv")
    return path

def get_db_path() -> str:
    cfg = get_config()
    return os.path.join(cfg.db_path, "wordsy.sqlite3")


def get_conn():
    """ Get connection to wordsy database. """
    path = get_db_path()
    logging.info(f"Wordsy database path ({path})")
    conn = sqlite3.connect(path)
    return conn

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP NOT NULL,
            word TEXT NOT NULL
        )
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
            tries TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_user_words_user_id ON user_words (user_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_user_words_word_id ON user_words (word_id)
    """)

    # Open friend request to another user
    cursor.execute("""
        CREATE TABLE friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            accepted_user_id INTEGER NOT NULL,
            sent_date TIMESTAMP NOT NULL,
            accepted_date TIMESTAMP,
            accepted BOOLEAN
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_friend_requests_user_id ON friend_requests (user_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_friend_requests_accepted_user_id ON friend_requests (accepted_user_id)
    """)

    # Tracks user friend relationships
    cursor.execute("""
        CREATE TABLE friends (
            friend_request_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            friend_user_id INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_friends_friend_request_id ON friends (friend_request_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_friends_user_id ON friends (user_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_friends_friend_user_id ON friends (friend_user_id)
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
