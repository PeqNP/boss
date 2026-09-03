#!/usr/bin/env python3
#
# Every reply that leaves the tree dirty carries a commit message.
#
# Runs on `Stop`, which fires when the assistant finishes a reply. It reads the
# reply out of the transcript and blocks when the working tree has changes and
# the reply carries no message for them.
#
# Blocking a `Stop` hands the reason back and the assistant keeps going, so the
# message is written before the turn ends rather than remembered afterwards.
#
# Reads the hook payload on stdin. Writes a decision on stdout.
#

import json
import os
import re
import subprocess
import sys

# The trailers a message ends with, and the shape of its subject line. A reply
# quoting one of these is a reply that wrote one.
TRAILER = re.compile(r"^(App|Feature|Decision):\s+\S", re.M)
SUBJECT = re.compile(r"^[a-z][\w.-]*: \S.{5,}$", re.M)


def dirty():
    """Paths the working tree has changed, ignoring what is untracked-and-ignored."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=os.getcwd()
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.split("\n") if line.strip()]


def last_reply(transcript_path):
    """The text of the most recent assistant message."""
    if not transcript_path or not os.path.exists(transcript_path):
        return ""
    said = []
    with open(transcript_path, encoding="utf-8") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = entry.get("message") or {}
            if message.get("role") != "assistant":
                continue
            content = message.get("content")
            if isinstance(content, str):
                said = [content]
            elif isinstance(content, list):
                text = [c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text"]
                if any(t.strip() for t in text):
                    said = text
    return "\n".join(said)


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    # A hook that blocked once already has said its piece.
    if payload.get("stop_hook_active"):
        return 0

    changed = dirty()
    if not changed:
        return 0

    reply = last_reply(payload.get("transcript_path"))
    if TRAILER.search(reply) and SUBJECT.search(reply):
        return 0

    listed = "\n".join(f"  {line}" for line in changed[:12])
    more = "" if len(changed) <= 12 else f"\n  ...and {len(changed) - 12} more"
    print(json.dumps({
        "decision": "block",
        "reason": (
            "The working tree has changes and this reply carries no commit "
            "message for them:\n"
            f"{listed}{more}\n\n"
            "Invoke the `commit` skill and print the message in the reply. It "
            "needs a `<area>: <subject>` line and the App/Feature/Decision "
            "trailers. Run `bin/check-commit` on it before printing it."
        )
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
