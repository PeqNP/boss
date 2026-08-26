# Reporting Work

Work gets a report. Any prompt that changed something ends this way, whatever
layer it touched — Python, JavaScript, Swift, a document, a tool.

## The sections, in this order

Paths and behaviour first, because that is what was asked for. What was learned
comes after. What the developer has to decide comes last, where they will still
be reading.

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
a check that turned out never to run, a counter nothing reads yet, a bug found
in passing.

Fill this by rereading the work rather than by recalling it.

### What I need from you

For a decision that is genuinely the developer's. Five short parts, in this
order, and the last two matter most:

- *The context.* Where the decision bites, in plain language.
- *What the source says.* Quote the plan's Open Decision, or the rule, verbatim
  — they wrote it, and the wording is the question.
- *Why it is a tradeoff.* Each option with its real consequence. Say which
  consequences are mild, because that is usually what decides it.
- *What is actually needed.* The question on its own, in a sentence.
- *What changes when they answer.* Which file, and what stands either way.

Recommend an option.

### Commit message

Last, in a fenced block, ready to paste.

## The commit message

It makes past work findable from `git log`.

Subject line: `<area>: <what changed>`, imperative, under 72 characters. Then a
blank line, then a short paragraph on *why* — the decision, rather than the
mechanics. Then trailers.

```
scheduler: link customer records to BOSS accounts on sign-in

A customer record is created when a booking is confirmed, and matched to
whoever it is for by account, then email, then phone. Reconciliation runs
when the app loads and on sign-in rather than being pushed from account
creation: the app already knows who is signed in, so there is no callback
to authenticate, deliver, or retry.

App: io.bithead.scheduler
Feature: customers
Feature: indexes
Decision: reconcile on app load rather than a service callback
Rule: every internal id is indexed, including composite-key trailers
Rule: build one model from another rather than copying fields
```

**Trailers.** `Key: value`, one per line, at the end. Repeat a key freely —
that is what makes them queryable. These four are the set:

| Key | What goes in it |
|---|---|
| `App` | Bundle id, when the work belongs to one app |
| `Feature` | The thing a person would search for later. One per line |
| `Decision` | A choice made that could reasonably have gone the other way |
| `Rule` | A rule written into `docs/prompt/` by this change |

Omit a key with nothing to say. Stretch for `Decision` and `Rule` — they answer
"why is it like this" long after the diff stops being readable.

Counts belong in the report above. A trailer carries what a future `git log`
would search for.

**What it buys:**

```bash
git log --grep="Feature: customers"        # every time we touched customers
git log --grep="^Decision:"                # every decision, ever
git log --grep="App: io.bithead.scheduler" # everything in one app
```

The developer commits. Write the message and hand it over.

## Notes

Report what happened. Failing tests come with their output. Work left aside is
named, with the reason.
