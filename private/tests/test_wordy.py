#!/usr/bin/env python3
#
# Tests all game related functions
#

import logging
import pytest

from libtest import *

lib = get_app_module("io.bithead.wordy")

logging.basicConfig(filename="unittests.log", encoding="utf-8", level=logging.INFO)

def test_game():
    lib.guess_word()

def test_friends():
    pass

def test_statistics():
    pass

def test_solver():
    pass

