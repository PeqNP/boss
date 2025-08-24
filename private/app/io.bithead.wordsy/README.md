# Wordsy

An open source version of Wordle.

## Prepare Application

Wordsy must have a database to derive word entries from. To do this, Wordsy derives words from the open source [Wordset Dictionary](https://github.com/wordset/wordset-dictionary) and creates a database based on those words.

If you want to re-create the database used by Wordsy, do the following:

- Clone the [Wordset Dictionary](https://github.com/wordset/wordset-dictionary)
- Install dependencies
    ```
    poetry install
    poetry run python -m spacy download en_core_web_sm
    ```
- Run `generate_wordsy_db.sh` to generate a new "wordsy" database
- (Re)start the service

> The scripts above do more than simply generate a database. For example, `create_dictionary.py` extracts only 5 letter words, with no spaces or special characters, and have no plural words that end in `s` or `es`. `create_words.py` creates random "word of day entries" using words from `dictionary.sqlite3`.

> `dictionary.sqlite3` is an intermediate database that can be removed after regenerating the database.

You can then run Wordsy by opening the Wordsy application from within BOSS.


