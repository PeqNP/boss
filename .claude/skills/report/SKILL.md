---
name: report
description: End a response that changed something with a report. Use after any prompt that edited a file, ran a migration, or changed behaviour — before handing anything back.
---

# Reporting work

Work gets a report. Any prompt that changed something ends this way, whatever
layer it touched — Python, JavaScript, Swift, a document, a tool.

## The sections, in this order

Paths and behaviour first — that is what was asked for. What was learned comes
after. What the developer has to decide comes last, where they will still be
reading.

### What was tested

One bullet per path, each reading *situation → outcome*. Happy paths and
exception paths in the same list, grouped by feature, and name the exception:

```
**Sending a verification code to get back into a booking**
- Customer gave a phone number → code sent by SMS
- Customer gave neither a phone nor an email → `NoContactChannel`, nothing sent
- Job code matches no appointment → `JobNotFound`, nothing sent
```

Where the work has no tests — a UI change, a document, a tool — this becomes
**What changed**, one bullet per thing, each written as behaviour:

```
- The Manage menu opens Setup Assistant last, after a separator
- A list box sized `auto` sits inside its window; `100%` overflows the border
```

### Tests

The total, and that they pass. State that each rule was broken deliberately and
a test caught it, with the mutation count.

Everything passes before moving on.

### What I found along the way

Mistakes made, surprises, anything left without a consumer. A wrong assertion,
a check that turned out to run on nothing, a counter nothing reads yet, a bug
found in passing.

Fill this by rereading the work.

### What I need from you

For a decision that is genuinely the developer's. Five short parts, in this
order, and the last two matter most:

- *The context.* Where the decision bites, in plain language.
- *What the source says.* Quote the plan's Open Decision, or the rule, verbatim
  — they wrote it, and the wording is the question.
- *Why it is a tradeoff.* Each option with its real consequence. Say which
  consequences are mild — that is usually what decides it.
- *What is actually needed.* The question on its own, in a sentence.
- *What changes when they answer.* Which file, and what stands either way.

Recommend an option.

### Commit message

Last, in a fenced block, ready to paste.

Write it with the `commit` skill, which reads the diff for the bullets and
runs `bin/check-commit`.

## Notes

Report what happened. Failing tests come with their output. Work left aside is
named, with the reason.
