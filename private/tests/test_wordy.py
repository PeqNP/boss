#!/usr/bin/env python3
#
# Tests all game related functions
#

import logging
import pytest

from libtest import *

get_app_module("io.bithead.wordy")
from io.bithead.wordy.lib import guess_word

logging.basicConfig(filename="unittests.log", encoding="utf-8", level=logging.INFO)

def test_game():
    guess_word("hello")

def test_friends():
    pass

def test_statistics():
    pass

def test_solver():
    pass

