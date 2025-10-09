#
# Wordy game logic.
#
# This layer is creatd to make it easier to test.
#

from .model import *

def guess_word(word: str) -> Puzzle:
    """
          // A full guess has not been provided
          if (guess.length != 5) {
            rattleGuess(guessNumber);
            return;
          }

          // NOTE: This will all be backend logic
          const lowered = guess.toLowerCase();
          const targetWord = "alert";
          // The number of times each letter shows up in the target word.
          const targetWordPattern = {
            "a": 1,
            "l": 1,
            "e": 1,
            "r": 1,
            "t": 1
          };

          let patternMatches = {};
          let matches = [];
          let numHits = 0;

          // Keyboard keys (letters) that were used during the solving of the puzzle
          let keys = [
            {
              "letter": "a",
              "state": "hit"
            },
            {
              "letter": "e",
              "state": "hit"
            },
            {
              "letter": "t",
              "state": "found"
            },
            {
              "letter": "k",
              "state": "miss"
            },
          ];

          for (let i = 0; i < guess.length; i++) {
            let letter = guess[i];

            // Increase by 1 the number of times this letter shows up in the guess
            if (letter in patternMatches) {
              patternMatches[letter] += 1;
            }
            else {
              patternMatches[letter] = 1;
            }

            if (letter == targetWord[i]) {
              numHits += 1;
              matches[i] = {
                "letter": letter,
                "state": "hit"
              }
            }
            else if (targetWord.includes(letter)) {
              // If this letter has been shown <= to the number of times the letter
              // appears in the target word, then it is found.
              if (patternMatches[letter] <= targetWordPattern[letter]) {
                matches[i] = {
                  "letter": letter,
                  "state": "found"
                }
              }
              else {
                matches[i] = {
                  "letter": letter,
                  "state": "miss"
                }
              }
            }
            else {
              matches[i] = {
                "letter": letter,
                "state": "miss"
              }
            }
          }
    """
    pass

