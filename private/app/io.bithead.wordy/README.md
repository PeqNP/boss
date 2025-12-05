# Wordy

An open source version of Wordle.

## Prepare Application

Wordy must have a database to derive word entries from. To do this, Wordy derives words from the open source [Wordset Dictionary](https://github.com/wordset/wordset-dictionary) and creates a database based on those words.

If you want to re-create the database used by Wordy, do the following:

- Clone the [Wordset Dictionary](https://github.com/wordset/wordset-dictionary)
- Install dependencies
    ```bash
    poetry install
    poetry run python -m spacy download en_core_web_sm
    poetry run python -m spacy download en_core_web_trf
    ```
- Run `bin/create_dictionary.py /path/to/wordset-dictionary` to generate the list of words that will be part of the Wordy database
- Start the service. If you have already started the service, you must remove the `wordy.sqlite3` database before restarting so that the database populates with the regenerated words.

You can then run Wordy by opening the Wordy application from within BOSS.

There is also a Berkly database on macOS whose license has ran out. You can generate the the list of words from this database using:

```bash
bin/create_dictionary.py /usr/share/dict/words
```

This is essentially a CSV file. Therefore, there is nothing stopping you from creating your own dictionary of words with a CSV. The only requirement is that the word is in the first column of the row.

## Run tests

```
cd /path/to/boss/private
./run_tests.sh tests/test_wordy.py
```
