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

import click


@click.command()
# help="Root path to Wordset Git repository"
@click.argument("db_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def main(db_path: str):
    click.echo(f"db_path: {db_path}")

if __name__ == '__main__':
    main()
