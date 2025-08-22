#!/usr/bin/env python3
#
# Generates a new database `dictionary.sqlite3`. This is an intermediate step
# to generate the final `wordsy.sqlite3` db used by the app.
#
# Creates a database consisting of
# - 5 letter words
# - Words that contain ASCII characters between a-zA-Z. In other words, no special characters, punctuation, etc.
# - Removes all plural words that end in `s` or `es` using NLP
#


