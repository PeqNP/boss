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
import csv
import json
import os
import spacy

nlp = spacy.load("en_core_web_sm")

IGNORE_WORDS = [
    "zombi",
    "aalii"
]


def print_lemma(word: str):
    """ Used to test if a word is a "real" word... or an alternate e.g. 'zombi' """
    doc = nlp(word)
    for token in doc:
        print(f"Text: {token.text}")
        print(f"Lemma: {token.lemma_}")
        print(f"Part of Speech (POS): {token.pos_}")
        print(f"Detailed POS Tag: {token.tag_}")
        print(f"Dependency Label: {token.dep_}")
        print(f"Morphology: {token.morph.to_dict()}")
        print(f"Is Alphabetic: {token.is_alpha}")
        print(f"Is Stop Word: {token.is_stop}")
        print(f"Entity Type: {token.ent_type_}")
        print("---")


def is_valid_plural(word: str):
    """ Determine if word is a valid plural (does not end with `s` or `es`)

    Returns: True when plural is a non plural word, or a plural word that does not end in `s` or `es`.
    """
    doc = nlp(word)
    for token in doc:
        # NOTE: NNS is tag for plural nouns
        if token.tag_ == "NNS" and word.endswith("es") or word.endswith("s"):
            return False
        # Ignore alternate spellings, e.g. "zombi", or words that are not
        # in any good dictionary.
        elif word in IGNORE_WORDS:
            return False
    return True


def create_dictionary_from_wordset(db_path: str):
    """ Create dictionary from open source Wordset dictionary. """
    # JSON files are in a directory called `data`
    data_path = os.path.join(db_path, "data")
    if not os.path.isdir(data_path):
        raise Exception(f"Could not find data path at ({data_path})")
    click.echo(f"Parsing dictionary from ({data_path})...")
    parsed_words = []
    total_words = 0
    kicked_out_words = 0
    kicked_out_plurals = 0
    with os.scandir(data_path) as entries:
        for entry in entries:
            if not entry.is_file():
                continue
            if not entry.path.endswith("json"):
                continue
            with open(entry.path, "r") as fh:
                try:
                    words = json.load(fh)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from ({file_path}) ({e})")
                    return None
                except Exception as e:
                    print(f"Error reading ({file_path}) ({e})")
                    return None
            total_words += len(words)
            # Every word is its own "key"
            for word in words.keys():
                # a-zA-Z
                if not word.isalpha():
                    kicked_out_words += 1
                    continue
                # Only 5 letter words
                if len(word) != 5:
                    kicked_out_words += 1
                    continue
                # Is not plural ending with `s` or `es`
                if not is_valid_plural(word):
                    kicked_out_words += 1
                    kicked_out_plurals += 1
                    continue
                parsed_words.append(word.lower())
    click.echo("Sorting words...")
    parsed_words.sort()
    click.echo(f"Found ({len(parsed_words)}) 5 letter words out of ({total_words}) total. Kicked ({kicked_out_words}) total words. Kicked ({kicked_out_plurals}) invalid plurals.")
    csv_file = "dictionary.csv"
    click.echo(f"Writing words to ({csv_file})...")
    with open(csv_file, "w") as fh:
        writer = csv.writer(fh)
        for word in parsed_words:
            writer.writerow([word])

def create_dictionary_from_csv(csv_path):
    """ Create dictionary from a list of words.

    Arguments:
        csv_path - Path to CSV with list of words. Expects every row to be a
            single word.
    """
    click.echo(f"Parsing CSV at ({csv_path})...")
    parsed_words = []
    total_words = 0
    kicked_out_words = 0
    kicked_out_plurals = 0
    with open(csv_path, "r") as fh:
        reader = csv.reader(fh)
        for row in reader:
            total_words += 1
            word = row[0]
            # a-zA-Z
            if not word.isalpha():
                kicked_out_words += 1
                continue
            # Only 5 letter words
            if len(word) != 5:
                kicked_out_words += 1
                continue
            # Is not plural ending with `s` or `es`
            if not is_valid_plural(word):
                kicked_out_words += 1
                kicked_out_plurals += 1
                continue
            parsed_words.append(word.lower())
    click.echo("Sorting words...")
    parsed_words.sort()
    click.echo(f"Found ({len(parsed_words)}) 5 letter words out of ({total_words}) total. Kicked ({kicked_out_words}) total words. Kicked ({kicked_out_plurals}) invalid plurals.")
    csv_file = "dictionary.csv"
    click.echo(f"Writing words to ({csv_file})...")
    with open(csv_file, "w") as fh:
        writer = csv.writer(fh)
        for word in parsed_words:
            writer.writerow([word])


@click.command()
# help="Root path to Wordset Git repository or path to CSV"
@click.argument("file_path", type=click.Path(exists=True, file_okay=True, dir_okay=True))
def main(file_path: str):
    if os.path.isfile(file_path):
        create_dictionary_from_csv(file_path)
    else:
        create_dictionary_from_wordset(file_path)

if __name__ == '__main__':
    main()
