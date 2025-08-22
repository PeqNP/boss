#!/bin/zsh
#
# Generates a new database used by the Wordsy app.
#
# This should only be ran once. Re-running will overwrite the entire database, and all attempts with it.
#

# Exit immediately if a command fails
set -e

# Generarte a dictionary of valid, five letter words
./bin/create_dictionary.py
# Generate the wordsy database with "Word of the day" entries
./bin/create_word_entries.py
# Remove intermediary database
rm dictionary.sqlite3
