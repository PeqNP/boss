---
name: report
description: End a response that changed something with a report. Use after any prompt that edited a file, ran a migration, or changed behaviour — before handing anything back.
---

# Reporting work

Four sections, in this order, and nothing else.

## 1. Summary title

An `##` heading naming what was added, then one line saying what it is.

```markdown
## Cover working days, time off, and the work an employee takes

Three UI tests added to flow 5, all mutation-verified.
```

The heading names the thing. `A feature that was never built` names nothing —
a reader cannot tell what it relates to. `An employee cannot be given access to
the app from any screen` names it.

A heading is a label, so it is named rather than written — see `shared.md`
§ Naming and writing are different jobs.

## 2. Lessons learned

What the developer did not know before this work. One lesson per entry,
separated by a blank line.

Each entry is a **bold sentence stating the lesson**, then the detail, then one
of two endings:

- **The solution performed.** What was done about it, in a sentence.
- **`I need your help:`** followed by the question, when no solution was
  derived. Say what is needed, not that something is difficult.

```markdown
**A token menu's options are `.ui-token-menu-option`, not `.option`.** I assumed
the list-box convention and the click timed out for 30 seconds. Solution: I
printed the rendered HTML of `.ui-token-menu-drop` and read the class off it
before writing the selector.

**`save the work an employee may be given` failed once, then passed five times.**
It timed out on `locator.click`, then passed in isolation, in two full-file runs
and through three mutation runs. No solution derived — I could not reproduce it.
**I need your help:** tell me if you see it fail again and I will chase the cause
rather than re-running.
```

A lesson is something that changes what somebody does next. These qualify:

- A selector, route, field or signature that was not what it looked like
- A defect found, and whether it was fixed
- A test that passed for the wrong reason, and what it asserts now
- Something specified and never built
- A mistake made, and what stopped it happening again
- A decision that is the developer's to make

## 3. Next

Where the work stands. One or two sentences: the next step, then what remains.

Read it off the app's `memory.md`, and the current `plan.md` while a stage is
open. Name the next stage, leftover, or decision. Say how much is left —
remaining stages, remaining leftovers, remaining flows — so a reader can tell
whether the plan is mid-flight or waiting on someone else.

```markdown
## Next

Stage 5 is next: wire the holiday routes. Two stages and the Holidays UI test
remain.
```

```markdown
## Next

Production Stripe and Twilio keys on Vendors. `plan.md` is finished; that
leftover is in `memory.md`.
```

A skill or docs change still names the next step of the app in play, when
there is one.

## 4. Commit

The message in a fenced block, written with the `commit` skill. The message
is this changeset — see the `commit` skill.

## What never appears in a report

- Narration of the steps taken. The commit bullets say what was done.
- Reasoning about why an approach was chosen, unless it is a lesson.
- Counts of tests passing, unless a test failed. Green is the default.
- Restating what the developer asked for.
- A section with nothing in it. Two lessons means two lessons.

Report failures with their output. Work left aside is named, with the reason.
