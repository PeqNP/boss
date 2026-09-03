---
name: commit
description: Write the commit message for work just finished. Use at the end of any prompt that changed a file, before handing the message to the developer.
---

# Writing a commit message

A subject line and a bulleted list. Nothing else — no paragraph, no trailers.

The `report` skill carries the report this message goes at the end of.

## 1. Read what changed

```bash
git diff --stat
git diff | grep "^[-+]def \|^[-+].*CREATE TABLE \|^[-+]@router\."
```

The second command lists the symbols that moved. Those are the bullets.

## 2. Check any claim before making it

`git show HEAD:<file>` settles what was already there — whether a column was
added or had been there all along.

## 3. Write it in the shape

Subject line: `<area>: <what changed>`, imperative, under 72 characters. Then a
blank line, then the bullets.

One bullet per thing accomplished, one line each, wrapped only where the line
would run past 72 characters. Each names what changed — a table, column,
function, route, index, file, or value — with the identifier backticked. A
consequence somewhere the diff does not touch gets a bullet of its own.

```
scheduler: cover working days, time off, and the work an employee takes

- Add `save a working day` to `uitest/tests/scheduler-employees.spec.js`
- Add `save time off` to it
- Add `save the work an employee may be given` to it
- Add an `openSaved` helper to it
- Record flow 5 as done in `ui-plan.md`, with deleting a working day and a
  time-off window still to cover
- Record the missing BOSS account picker as a finding in `ui-plan.md`
- Record it in `review.md` under built on the server, missing from a screen
```

**Name every removal.** A removal exists only in history, so one a message
leaves out is findable by nobody.

## 4. Run it before handing it over

```bash
bin/check-commit <message-file>            # against the working tree
bin/check-commit --cached <message-file>   # against what is staged
```

It reads the diff and reports removals the message does not name.

## What never appears in a commit message

- A paragraph explaining the symptom or the reasoning. That belongs in the
  report's lessons, where the developer reads it once.
- Counts, timings, or that tests pass.
- Which files were read to work it out.
