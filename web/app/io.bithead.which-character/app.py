#!/usr/bin/env python3
#
# Ask AI which character a user resembles from list of
# supported TV shows.
#

import requests

# TODO: Multi-modal support isn't ready yet. This is some dummy code that may
# work once it becomes available.

api_key = ""
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "multipart/form-data"
}

data = {
    "model": "grok-vision",  # TODO: Assumes this is the name for the multi-modal model
    "prompt": "Which character from 'The Office' does this person resemble?",
}

files = {
    "image": open("/path/to/user_image.jpg", "rb")
}

response = requests.post('https://api.x.ai/v1/vision', headers=headers, data=data, files=files)

print(response.json())
