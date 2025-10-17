#!/usr/bin/env python3
#
# Generates a new database `dictionary.sqlite3`. This is an intermediate step
# to generate the final `wordsy.sqlite3` db used by the app.
#
# This assumes words within the database are proper names if the first letter is capitalized.
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

# en_core_web_sm = efficiency
# en_core_web_trf = accuracy
nlp = spacy.load("en_core_web_trf")

IGNORE_WORDS = [
    "zombi",
    "aalii"
]

# TODO: Words that will be included, regardless of NLP.
INCLUDE_WORDS = [
    "emote"
]

def is_valid_word(doc: any) -> bool:
    """ Determine if word is a valid plural (does not end with `s` or `es`)
    and not a name.

    Returns: True when plural is a non plural word, or a plural word that does not end in `s` or `es`.
    """
    for token in doc:
        word = token.text
        # NOTE: NNS is tag for plural nouns
        if token.tag_ == "NNS" and (word.endswith("es") or word.endswith("s")):
            return False
        # Out of vocabulary. Always returns True for words tested in isolation.
        #if token.is_oov:
        #    return False
        # Low probability of being an English word. Probably the same problem
        # as is_oov.
        #if token.prob < -9:
        #    return False
        # Ignore names of people
        # NOTE: "PERSON" is disabled because dictionary words capitalize proper
        # nouns. At this point, any word that has an uppercase value has been
        # kicked out of the set before NLP.
        elif token.ent_type_ in ["ORG"]:
            return False
        # Proper names are almost always names of persons, places, or things. Some names,
        # such as "Eloha" seem to be misclassified as "ORDINAL" entity types. This pass
        # ensures names are not included.
        #
        # This may still incorrectly align certain words like `emote` as a proper
        # noun. For example, `emote` can be a verb, but is classified as a
        # "proper noun" when compared by itself. Presumably because it's used as
        # a way to name certain things e.g. "Emote pack"
        elif token.pos_ in ["PROPN"] and token.ent_type_ in ["ORDINAL"]:
            return False

        # Ignore alternate spellings, e.g. "zombi", or words that are not
        # in any good dictionary.
        elif word in IGNORE_WORDS:
            return False
    return True

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

"""
print_lemma("frail")
import sys
sys.exit(0)
"""

def is_name(word: str) -> bool:
    """ Returns true if `word` is a name. """
    pass

def create_dictionary_from_wordset(db_path: str):
    """ Create dictionary from open source Wordset dictionary. """
    # JSON files are in a directory called `data`
    data_path = os.path.join(db_path, "data")
    if not os.path.isdir(data_path):
        raise Exception(f"Could not find data path at ({data_path})")
    click.echo(f"Parsing dictionary from ({data_path})...")
    words = set()
    total_words = 0
    kicked_out_words = 0
    kicked_out_invalid = 0
    with os.scandir(data_path) as entries:
        for entry in entries:
            if not entry.is_file():
                continue
            if not entry.path.endswith("json"):
                continue
            with open(entry.path, "r") as fh:
                try:
                    dict_words = json.load(fh)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from ({file_path}) ({e})")
                    return
                except Exception as e:
                    print(f"Error reading ({file_path}) ({e})")
                    return
            total_words += len(dict_words)
            # Every word is its own "key"
            for word in dict_words.keys():
                # a-zA-Z
                if not word.isalpha():
                    kicked_out_words += 1
                    continue
                # Only 5 letter words
                if len(word) != 5:
                    kicked_out_words += 1
                    continue
                # Proper noun
                if word.lower() != word:
                    kicked_out_words += 1
                    kicked_out_invalid += 1
                    continue
                words.add(word.lower())

    words = list(words)

    click.echo("NLP in progress...")
    docs = list(nlp.pipe(words, n_process=-1, batch_size=200))
    parsed_words = [doc.text for doc in docs if is_valid_word(doc)]
    num_words_removed = len(words) - len(docs)
    kicked_out_words += num_words_removed
    kicked_out_invalid += num_words_removed

    click.echo("Sorting words...")
    parsed_words = list(parsed_words)
    parsed_words.sort()

    click.echo("Writing words...")
    csv_file = "dictionary.csv"
    click.echo(f"Writing words to ({csv_file})...")
    with open(csv_file, "w") as fh:
        writer = csv.writer(fh)
        for word in parsed_words:
            writer.writerow([word])
    click.echo(f"Found ({len(parsed_words)}) 5 letter words out of ({total_words}) total. Kicked ({kicked_out_words}) total words. Kicked ({kicked_out_invalid}) plural and proper nouns.")

def create_dictionary_from_csv(csv_path):
    """ Create dictionary from a list of words.

    Arguments:
        csv_path - Path to CSV with list of words. Expects every row to be a
            single word.
    """
    click.echo(f"Parsing CSV at ({csv_path})...")
    words = set()
    total_words = 0
    kicked_out_words = 0
    kicked_out_invalid = 0
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
            # If word is capitalized in any way, this algo assumes the word is a
            # proper noun w/o attempting to perform NLP.
            if word.lower() != word:
                kicked_out_words += 1
                kicked_out_invalid += 1
                continue
            words.add(word.lower())

    words = list(words)

    click.echo("NLP in progress...")
    docs = list(nlp.pipe(words, n_process=-1, batch_size=200))
    parsed_words = [doc.text for doc in docs if is_valid_word(doc)]
    num_words_removed = len(words) - len(docs)
    kicked_out_words += num_words_removed
    kicked_out_invalid += num_words_removed

    click.echo("Sorting words...")
    parsed_words.sort()

    click.echo("Writing words...")
    csv_file = "dictionary.csv"
    click.echo(f"Writing words to ({csv_file})...")
    with open(csv_file, "w") as fh:
        writer = csv.writer(fh)
        for word in parsed_words:
            writer.writerow([word])
    click.echo(f"Found ({len(parsed_words)}) 5 letter words out of ({total_words}) total. Kicked ({kicked_out_words}) total words. Kicked ({kicked_out_invalid}) plural and proper nouns.")

# help="Root path to Wordset Git repository or path to CSV"
@click.command()
@click.argument("file_path", type=click.Path(exists=True, file_okay=True, dir_okay=True))
def main(file_path: str):
    if os.path.isfile(file_path):
        create_dictionary_from_csv(file_path)
    else:
        create_dictionary_from_wordset(file_path)

if __name__ == '__main__':
    main()
